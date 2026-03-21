"""Nester Agent — multi-timeframe interval nesting (区间套) with tool use.

Uses Claude tool_use to autonomously:
1. Fetch multi-timeframe data via run_pipeline tool
2. Analyze signals across timeframes
3. Determine direction alignment and precise entry points

Falls back to deterministic nesting when LLM is unavailable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from chanquant.agents.bedrock import create_model
from chanquant.agents.prompts import load_prompt
from chanquant.agents.state import SystemState
from chanquant.agents.tool_executor import run_agent_with_tools
from chanquant.agents.tool_defs import clear_cache, execute_tool
from chanquant.core.nesting import IntervalNester
from chanquant.core.objects import Signal, SignalType, TimeFrame


class _PerLevelInfo(BaseModel):
    """Per-timeframe direction info."""
    trend: Optional[str] = None
    direction: Optional[str] = None
    signal: Optional[str] = None
    has_structure: bool = False


class _NestingLLMResponse(BaseModel):
    """Schema for validating LLM nesting analysis JSON output."""
    instrument: str = ""
    nesting_path: list[str] = Field(default_factory=list)
    per_level: dict[str, _PerLevelInfo] = Field(default_factory=dict)
    target_level: str = ""
    large_signal: Optional[str] = None
    medium_signal: Optional[str] = None
    precise_signal: Optional[str] = None
    nesting_depth: int = Field(default=0, ge=0, le=10)
    direction_aligned: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    actionable: bool = False
    status: str = ""
    risk_assessment: str = ""
    reasoning: str = ""


_NESTING_SYSTEM_PROMPT = """\
你是区间套分析Agent。使用缠论多级别区间套定位精确买卖点。

## 工具
- **run_pipeline**: 运行缠论L0-L7分析管道（含趋势、中枢、背驰、信号）
- **compare_divergence**: 比较两个级别的背驰状态
- **get_market_summary**: 获取全级别概览（1w/1d/30m/5m）

## 分析流程

### 第一步：全局概览
调用 `get_market_summary` 获取所有级别状态。

### 第二步：从大到小分析
- 周线(1w): 总体方向和趋势阶段
- 日线(1d): 周线趋势中的当前位置，寻找信号
- 30分钟(30m): 日线走势中的精确位置（若无结构则使用15m或1h）
- 5分钟(5m): 执行时机

### 第三步：对齐检查
- 所有级别均为买入信号 → 强买入，高置信度
- 大级别买+小级别卖 → 等待，不操作
- 大级别卖+小级别买 → 禁止操作（规则8.5否决）

### 第四步：硬规则
- 嵌套深度 < 2 → actionable=false，status="观察中"
- 嵌套深度 ≥ 2 且方向一致 → 可操作
- 过时信号无效：周线>6个月、日线>30天、30m>5天、5m>2天的信号视为过时，不作为决策依据

### 第五步：综合输出
**所有文字输出必须使用中文**，结构化为：结论→依据→风险

## 输出格式 (工具调用完成后的最终JSON)
```json
{
  "instrument": "...",
  "nesting_path": ["1w:up_trend", "1d:down_trend:S2", "30m:consolidation", "5m:no_data"],
  "per_level": {
    "1w": {"trend": "up_trend", "direction": "多", "signal": null, "has_structure": true},
    "1d": {"trend": "down_trend", "direction": "空", "signal": "S2", "has_structure": true},
    "30m": {"trend": null, "direction": null, "signal": null, "has_structure": false},
    "5m": {"trend": null, "direction": null, "signal": null, "has_structure": false}
  },
  "target_level": "1d",
  "large_signal": "S2",
  "medium_signal": null,
  "precise_signal": null,
  "nesting_depth": 1,
  "direction_aligned": false,
  "confidence": 0.3,
  "actionable": false,
  "status": "观察中 — 仅单级别确认，不建议操作",
  "risk_assessment": "仅日线有信号，30m/5m无结构确认，操作风险较高",
  "reasoning": "结论：当前不建议操作\\n依据：周线上升趋势中，日线出现S2卖点但仅单级别确认\\n风险：30分钟级别无有效结构，无法精确定位"
}
```
"""


class NesterAgent:
    """Interval nesting agent with LLM tool use + deterministic fallback."""

    def __init__(self, use_llm: bool = True) -> None:
        self._use_llm = use_llm
        self._nester = IntervalNester()
        self._model = None
        if use_llm:
            try:
                self._model = create_model("nester")
            except Exception:
                self._use_llm = False

    def run(self, state: SystemState) -> SystemState:
        """Process scan results and produce nested signals."""
        scan_results = state.get("scan_results", [])
        if not scan_results:
            state["current_phase"] = "score"
            return state

        # Group signals by instrument
        by_instrument: dict[str, list[dict]] = {}
        for sr in scan_results:
            inst = sr["instrument"]
            by_instrument.setdefault(inst, []).append(sr)

        nested_signals: list[dict] = []
        errors = list(state.get("errors", []))

        clear_cache()  # fresh data each run

        for instrument, signals in by_instrument.items():
            try:
                if self._use_llm and self._model is not None:
                    result = self._tool_use_nesting(instrument, signals)
                else:
                    result = self._deterministic_nesting(instrument, signals)
                if result is not None:
                    nested_signals.append(result)
            except Exception as exc:
                errors.append(f"nester:{instrument}:{exc}")
                try:
                    result = self._deterministic_nesting(instrument, signals)
                    if result is not None:
                        nested_signals.append(result)
                except Exception:
                    pass

        state["nested_signals"] = nested_signals
        state["current_phase"] = "score"
        state["errors"] = errors
        return state

    def analyze_instrument(self, instrument: str) -> dict[str, Any] | None:
        """Standalone multi-TF nesting analysis for a single instrument.

        Can be called directly from the API for on-demand analysis.
        """
        clear_cache()

        if self._use_llm and self._model is not None:
            return self._tool_use_nesting(instrument, [])
        return self._deterministic_multi_tf(instrument)

    def _tool_use_nesting(
        self, instrument: str, signals: list[dict]
    ) -> dict[str, Any] | None:
        """Use LLM with tool_use for multi-timeframe nesting."""
        if self._model is None:
            return self._deterministic_nesting(instrument, signals)

        # Build user message
        signal_summary = ""
        if signals:
            signal_summary = (
                f"\nExisting scan results for {instrument}:\n"
                + json.dumps(signals, indent=2, default=str)
            )

        user_msg = (
            f"Perform interval nesting analysis for {instrument}.\n"
            f"Use your tools to fetch and analyze multi-timeframe data.\n"
            f"Start with get_market_summary, then drill into specific timeframes as needed."
            f"{signal_summary}"
        )

        try:
            result = run_agent_with_tools(
                model=self._model,
                system_prompt=_NESTING_SYSTEM_PROMPT,
                user_message=user_msg,
                max_iterations=6,
            )

            parsed = self._parse_response(instrument, result["response"])
            if parsed is not None:
                parsed["tool_calls"] = result["tool_calls"]
                parsed["iterations"] = result["iterations"]
                parsed["confidence_source"] = "llm_tool_use"
            return parsed

        except Exception:
            return self._deterministic_nesting(instrument, signals)

    # Per-TF kline limits — small TFs need more bars to build structure
    _TF_LIMITS: dict[str, int] = {
        "1w": 500, "1d": 500, "1h": 2000,
        "30m": 2000, "15m": 3000, "5m": 3000,
    }

    # Max signal age per TF — signals older than this are stale and ignored
    _SIGNAL_MAX_AGE: dict[str, timedelta] = {
        "1w": timedelta(weeks=26),   # ~6 months
        "1d": timedelta(days=30),    # 1 month
        "1h": timedelta(days=7),     # 1 week
        "30m": timedelta(days=5),    # 5 days
        "15m": timedelta(days=3),    # 3 days
        "5m": timedelta(days=2),     # 2 days
    }

    @staticmethod
    def _filter_stale_signals(
        signals: list[dict], max_age: timedelta, now: datetime,
    ) -> list[dict]:
        """Remove signals older than max_age."""
        cutoff = now - max_age
        result = []
        for s in signals:
            ts_str = s.get("timestamp", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    result.append(s)
            except (ValueError, TypeError):
                continue
        return result

    def _deterministic_multi_tf(self, instrument: str) -> dict[str, Any] | None:
        """Deterministic multi-TF analysis: run pipeline for each TF, synthesize."""
        results: dict[str, dict] = {}
        primary_tfs = ["1w", "1d", "30m", "5m"]

        for tf_str in primary_tfs:
            limit = self._TF_LIMITS.get(tf_str, 500)
            result = execute_tool("run_pipeline", {
                "instrument": instrument, "timeframe": tf_str, "limit": limit,
            })
            if not result.get("error"):
                results[tf_str] = result

        # Fallback: if 30m has no structure, try 15m then 1h
        r30 = results.get("30m", {})
        if r30.get("segment_count", 0) == 0 and r30.get("center_count", 0) == 0:
            for fallback_tf in ["15m", "1h"]:
                limit = self._TF_LIMITS.get(fallback_tf, 2000)
                fb_result = execute_tool("run_pipeline", {
                    "instrument": instrument, "timeframe": fallback_tf, "limit": limit,
                })
                if not fb_result.get("error") and (
                    fb_result.get("segment_count", 0) > 0
                    or fb_result.get("center_count", 0) > 0
                ):
                    results[fallback_tf] = fb_result
                    # Replace 30m in the chain
                    if "30m" in results:
                        del results["30m"]
                    primary_tfs = ["1w", "1d", fallback_tf, "5m"]
                    break

        if not results:
            return None

        # Build per-level direction info and nesting path
        nesting_path = []
        per_level_direction: dict[str, dict] = {}
        all_signals: dict[str, list[dict]] = {}
        now = datetime.now(timezone.utc)

        for tf_str in primary_tfs:
            result = results.get(tf_str)
            if not result:
                nesting_path.append(f"{tf_str}:no_data")
                per_level_direction[tf_str] = {
                    "trend": None, "direction": None,
                    "signal": None, "has_structure": False,
                }
                continue

            trend = result.get("trend", {})
            trend_cls = trend.get("classification", "unknown") if trend else "no_data"
            sigs = result.get("signals", [])

            # Sort signals by timestamp descending to find the most recent
            sigs_sorted = sorted(
                sigs,
                key=lambda s: s.get("timestamp", ""),
                reverse=True,
            )

            # Filter out stale signals based on timeframe-specific max age
            max_age = self._SIGNAL_MAX_AGE.get(tf_str, timedelta(days=30))
            sigs_sorted = self._filter_stale_signals(sigs_sorted, max_age, now)

            sig_types = [s["signal_type"] for s in sigs_sorted]

            path_entry = f"{tf_str}:{trend_cls}"
            if sig_types:
                path_entry += f":{','.join(sig_types)}"
            nesting_path.append(path_entry)

            # Per-level direction: use trend first, then MOST RECENT signal
            direction = None
            if trend_cls in ("up_trend",):
                direction = "多"
            elif trend_cls in ("down_trend",):
                direction = "空"
            elif sigs_sorted:
                latest = sigs_sorted[0]
                direction = "多" if latest["signal_type"] in ("B1", "B2", "B3") else "空"

            latest_sig_type = sigs_sorted[0]["signal_type"] if sigs_sorted else None

            has_structure = (
                result.get("segment_count", 0) > 0
                or result.get("center_count", 0) > 0
            )
            per_level_direction[tf_str] = {
                "trend": trend_cls,
                "direction": direction,
                "signal": latest_sig_type,
                "has_structure": has_structure,
            }

            if sigs_sorted:
                all_signals[tf_str] = sigs_sorted

        # Find levels with signals
        found_levels: list[str] = [
            lvl for lvl in primary_tfs if lvl in all_signals and all_signals[lvl]
        ]

        if not found_levels:
            return {
                "instrument": instrument,
                "nesting_path": nesting_path,
                "per_level": per_level_direction,
                "target_level": "1d",
                "large_signal": None, "medium_signal": None, "precise_signal": None,
                "nesting_depth": 0,
                "direction_aligned": False,
                "confidence": "0",
                "actionable": False,
                "status": "观察中 — 无活跃信号",
                "confidence_source": "deterministic_multi_tf",
            }

        large_sig = all_signals[found_levels[0]][0]  # most recent (sorted desc)
        medium_sig = all_signals[found_levels[1]][0] if len(found_levels) >= 2 else None
        precise_sig = all_signals[found_levels[2]][0] if len(found_levels) >= 3 else None

        def is_buy(s: dict) -> bool:
            return s.get("signal_type", "") in ("B1", "B2", "B3")

        aligned = True
        if large_sig and medium_sig:
            aligned = is_buy(large_sig) == is_buy(medium_sig)
        if aligned and large_sig and precise_sig:
            aligned = is_buy(large_sig) == is_buy(precise_sig)

        depth = len(found_levels)
        confidence = min(1.0, depth * 0.3 + (0.2 if aligned else 0))

        # Hard rule: depth < 2 → observation only
        actionable = depth >= 2 and confidence >= 0.4
        if depth < 2:
            status = "观察中 — 仅单级别确认，不建议操作"
        elif not aligned:
            status = "观察中 — 多级别方向不一致"
        elif confidence < 0.4:
            status = "观察中 — 置信度不足"
        else:
            direction_word = "做多" if is_buy(large_sig) else "做空"
            status = f"可操作 — {depth}层确认{direction_word}"

        return {
            "instrument": instrument,
            "nesting_path": nesting_path,
            "per_level": per_level_direction,
            "target_level": found_levels[-1],
            "large_signal": large_sig["signal_type"],
            "medium_signal": medium_sig["signal_type"] if medium_sig else None,
            "precise_signal": precise_sig["signal_type"] if precise_sig else None,
            "nesting_depth": depth,
            "direction_aligned": aligned,
            "confidence": str(confidence),
            "actionable": actionable,
            "status": status,
            "confidence_source": "deterministic_multi_tf",
        }

    def _deterministic_nesting(
        self, instrument: str, signals: list[dict]
    ) -> dict[str, Any] | None:
        """Fallback: deterministic nesting from pre-scanned signals only."""
        by_level: dict[str, list[dict]] = {}
        for s in signals:
            by_level.setdefault(s["level"], []).append(s)

        level_order = ["1M", "1w", "1d", "30m", "5m", "1m"]
        found_levels: list[str] = [
            lvl for lvl in level_order if lvl in by_level
        ]

        if not found_levels:
            return None

        large_sig = by_level[found_levels[0]][0]
        medium_sig = by_level[found_levels[1]][0] if len(found_levels) >= 2 else None
        precise_sig = by_level[found_levels[2]][0] if len(found_levels) >= 3 else None

        def is_buy(s: dict) -> bool:
            return s["signal_type"] in ("B1", "B2", "B3")

        aligned = True
        if medium_sig and is_buy(large_sig) != is_buy(medium_sig):
            aligned = False
        if precise_sig and is_buy(large_sig) != is_buy(precise_sig):
            aligned = False

        depth = len(found_levels)
        confidence = min(1.0, depth * 0.3 + (0.2 if aligned else 0))

        # Hard rule: depth < 2 → observation only
        actionable = depth >= 2 and confidence >= 0.4
        if depth < 2:
            status = "观察中 — 仅单级别确认，不建议操作"
        elif not aligned:
            status = "观察中 — 多级别方向不一致"
        elif confidence < 0.4:
            status = "观察中 — 置信度不足"
        else:
            direction_word = "做多" if is_buy(large_sig) else "做空"
            status = f"可操作 — {depth}层确认{direction_word}"

        return {
            "instrument": instrument,
            "target_level": found_levels[-1],
            "large_signal": large_sig["signal_type"],
            "medium_signal": medium_sig["signal_type"] if medium_sig else None,
            "precise_signal": precise_sig["signal_type"] if precise_sig else None,
            "nesting_depth": depth,
            "direction_aligned": aligned,
            "confidence": str(confidence),
            "actionable": actionable,
            "status": status,
            "confidence_source": "deterministic_fallback",
        }

    def _parse_response(
        self, instrument: str, response: str
    ) -> dict[str, Any] | None:
        """Parse and validate LLM response JSON against Pydantic schema."""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start < 0 or end <= start:
                return None
            raw = json.loads(response[start:end])
            validated = _NestingLLMResponse(**raw)
            data = validated.model_dump()
            data["instrument"] = instrument
            data["confidence"] = str(data["confidence"])
            # Convert _PerLevelInfo objects to plain dicts
            if data.get("per_level"):
                data["per_level"] = {
                    k: v if isinstance(v, dict) else v
                    for k, v in data["per_level"].items()
                }
            return data
        except (json.JSONDecodeError, ValidationError, ValueError):
            return None
