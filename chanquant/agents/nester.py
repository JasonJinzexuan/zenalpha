"""Nester Agent — multi-timeframe interval nesting (区间套) with tool use.

Uses Claude tool_use to autonomously:
1. Fetch multi-timeframe data via run_pipeline tool
2. Analyze signals across timeframes
3. Determine direction alignment and precise entry points

Falls back to deterministic nesting when LLM is unavailable.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from chanquant.agents.bedrock import create_model
from chanquant.agents.prompts import load_prompt
from chanquant.agents.state import SystemState
from chanquant.agents.tool_executor import run_agent_with_tools
from chanquant.agents.tool_defs import clear_cache, execute_tool
from chanquant.core.nesting import IntervalNester
from chanquant.core.objects import Signal, SignalType, TimeFrame


class _NestingLLMResponse(BaseModel):
    """Schema for validating LLM nesting analysis JSON output."""
    instrument: str = ""
    nesting_path: list[str] = Field(default_factory=list)
    target_level: str = ""
    large_signal: Optional[str] = None
    medium_signal: Optional[str] = None
    precise_signal: Optional[str] = None
    nesting_depth: int = Field(default=0, ge=0, le=10)
    direction_aligned: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_assessment: str = ""
    reasoning: str = ""


_NESTING_SYSTEM_PROMPT = """\
You are the Nesting Agent (区间套分析Agent). You perform multi-timeframe interval nesting \
to precisely locate entry/exit points using Chan Theory (缠论).

## Your Tools

You have access to these tools:
- **run_pipeline**: Run the deterministic Chan Theory L0-L7 pipeline on a specific \
instrument and timeframe. Returns trend, centers, divergences, and signals.
- **compare_divergence**: Compare divergence status between two timeframes.
- **get_market_summary**: Get a quick overview across all timeframes (1w/1d/30m/5m).

## Multi-Timeframe Nesting Process

### Step 1: Get the big picture
Call `get_market_summary` for the instrument to see all timeframes at once.

### Step 2: Analyze from large to small
- Weekly (1w): Overall direction and trend stage
- Daily (1d): Current position within weekly trend, look for signals
- 30-minute (30m): Precision within daily move
- 5-minute (5m): Execution timing

### Step 3: Alignment check
- All timeframes showing buy signals → STRONG BUY, high confidence
- Large=buy + small=sell → Wait, don't trade
- Large=sell + small=buy → DO NOT TRADE (veto per rule 8.5)

### Step 4: Synthesize
Produce your final nesting analysis with:
- Direction alignment across timeframes
- Precise entry signal (from smallest timeframe with a signal)
- Confidence based on alignment depth
- Risk assessment

## Output Format (final response after tool use)
```json
{
  "instrument": "...",
  "nesting_path": ["1w:UP_TREND", "1d:B3", "30m:CONSOLIDATION", "5m:no_signal"],
  "target_level": "1d",
  "large_signal": "B3" or null,
  "medium_signal": null,
  "precise_signal": null,
  "nesting_depth": 1,
  "direction_aligned": true,
  "confidence": 0.7,
  "risk_assessment": "...",
  "reasoning": "step-by-step nesting logic"
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

    def _deterministic_multi_tf(self, instrument: str) -> dict[str, Any] | None:
        """Deterministic multi-TF analysis: run pipeline for each TF, synthesize."""
        results: dict[str, dict] = {}
        for tf_str in ["1w", "1d", "30m", "5m"]:
            result = execute_tool("run_pipeline", {
                "instrument": instrument, "timeframe": tf_str
            })
            if not result.get("error"):
                results[tf_str] = result

        if not results:
            return None

        # Find signals across timeframes
        nesting_path = []
        all_signals: dict[str, list[dict]] = {}
        for tf_str, result in results.items():
            trend = result.get("trend", {})
            trend_cls = trend.get("classification", "unknown") if trend else "no_data"
            sigs = result.get("signals", [])
            sig_types = [s["signal_type"] for s in sigs]

            path_entry = f"{tf_str}:{trend_cls}"
            if sig_types:
                path_entry += f":{','.join(sig_types)}"
            nesting_path.append(path_entry)

            if sigs:
                all_signals[tf_str] = sigs

        # Find largest and smallest TF with signals
        level_order = ["1w", "1d", "30m", "5m"]
        large_sig = None
        medium_sig = None
        precise_sig = None
        found_levels: list[str] = []

        for lvl in level_order:
            if lvl in all_signals and all_signals[lvl]:
                found_levels.append(lvl)

        if not found_levels:
            return {
                "instrument": instrument,
                "nesting_path": nesting_path,
                "target_level": "1d",
                "large_signal": None,
                "medium_signal": None,
                "precise_signal": None,
                "nesting_depth": 0,
                "direction_aligned": False,
                "confidence": "0",
                "confidence_source": "deterministic_multi_tf",
            }

        large_sig = all_signals[found_levels[0]][-1] if found_levels else None
        if len(found_levels) >= 2:
            medium_sig = all_signals[found_levels[1]][-1]
        if len(found_levels) >= 3:
            precise_sig = all_signals[found_levels[2]][-1]

        def is_buy(s: dict) -> bool:
            return s.get("signal_type", "") in ("B1", "B2", "B3")

        aligned = True
        if large_sig and medium_sig:
            aligned = is_buy(large_sig) == is_buy(medium_sig)
        if aligned and large_sig and precise_sig:
            aligned = is_buy(large_sig) == is_buy(precise_sig)

        depth = len(found_levels)
        confidence = min(1.0, depth * 0.3 + (0.2 if aligned else 0))

        return {
            "instrument": instrument,
            "nesting_path": nesting_path,
            "target_level": found_levels[-1],
            "large_signal": large_sig["signal_type"] if large_sig else None,
            "medium_signal": medium_sig["signal_type"] if medium_sig else None,
            "precise_signal": precise_sig["signal_type"] if precise_sig else None,
            "nesting_depth": depth,
            "direction_aligned": aligned,
            "confidence": str(confidence),
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
        confidence = str(min(1.0, depth * 0.3 + (0.2 if aligned else 0)))

        return {
            "instrument": instrument,
            "target_level": found_levels[-1],
            "large_signal": large_sig["signal_type"],
            "medium_signal": medium_sig["signal_type"] if medium_sig else None,
            "precise_signal": precise_sig["signal_type"] if precise_sig else None,
            "nesting_depth": depth,
            "direction_aligned": aligned,
            "confidence": confidence,
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
            return data
        except (json.JSONDecodeError, ValidationError, ValueError):
            return None
