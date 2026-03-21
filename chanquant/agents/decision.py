"""Trading Decision Agent — synthesizes signals + macro into actionable decisions.

Combines:
- Multi-TF nesting analysis (Chan Theory signals)
- Macro economic news/events
- Produces: BUY (with price range), SELL (with price range), or NO_ACTION
Only records decisions that require action.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from chanquant.agents.bedrock import create_model, ModelConfig, ModelTier
from chanquant.agents.nester import NesterAgent
from chanquant.agents.tool_defs import clear_cache, _get_klines_sync
from chanquant.risk.conflict import resolve_conflicts
from chanquant.risk.manager import RiskManager
from chanquant.strategy.models import StrategyParams, RiskParams
from chanquant.strategy.templates import get_template, MODERATE

logger = logging.getLogger(__name__)


class TradingDecision(BaseModel):
    """A single trading decision record."""

    instrument: str
    timestamp: str  # ISO 8601
    action: str  # "BUY" | "SELL" | "NO_ACTION"
    price_current: str = ""
    price_range_low: str = ""
    price_range_high: str = ""
    stop_loss: str = ""
    position_size: str = ""  # e.g. "30%" of portfolio
    urgency: str = ""  # "立即" | "等待回调" | "观察"
    confidence: float = 0.0
    signal_basis: str = ""  # which signals triggered this
    macro_context: str = ""  # macro factors considered
    reasoning: str = ""  # structured: 结论→依据→风险
    nesting_summary: dict[str, Any] = Field(default_factory=dict)


class DecisionAgent:
    """Produces actionable trading decisions from nesting analysis + macro."""

    def __init__(
        self,
        use_llm: bool = True,
        strategy_name: str | None = None,
    ) -> None:
        self._use_llm = use_llm
        self._nester = NesterAgent(use_llm=False)  # deterministic for speed
        self._risk_manager = RiskManager()
        # Load strategy + risk params separately
        if strategy_name:
            tmpl = get_template(strategy_name)
            self._strategy = tmpl.strategy if tmpl else MODERATE.strategy
            self._risk = tmpl.risk if tmpl else MODERATE.risk
        else:
            self._strategy = MODERATE.strategy
            self._risk = MODERATE.risk
        self._model = None
        if use_llm:
            try:
                self._model = create_model(
                    "decision",
                    ModelConfig(tier=ModelTier.SONNET, max_tokens=4096),
                )
            except Exception:
                self._use_llm = False

    @staticmethod
    def _fetch_current_price(instrument: str) -> str:
        """Get the latest close price from 5m klines."""
        try:
            klines = _get_klines_sync(instrument, "5m", 1)
            if klines:
                return str(klines[-1].close)
        except Exception:
            pass
        return ""

    def analyze(
        self,
        instrument: str,
        macro_news: list[dict[str, Any]] | None = None,
    ) -> TradingDecision | None:
        """Run full decision analysis for one instrument.

        Returns None if no action needed, TradingDecision otherwise.
        """
        clear_cache()

        # 1. Get nesting analysis
        nesting = self._nester.analyze_instrument(instrument)
        if nesting is None:
            return None

        # 2. Build context
        now = datetime.now(timezone.utc).isoformat()
        current_price = self._fetch_current_price(instrument)

        news = macro_news or []
        if self._use_llm and self._model is not None:
            return self._llm_decision(instrument, nesting, news, now, current_price)
        return self._deterministic_decision(instrument, nesting, now, news, current_price)

    def analyze_batch(
        self,
        instruments: list[str],
        macro_news: list[dict[str, Any]] | None = None,
    ) -> list[TradingDecision]:
        """Analyze multiple instruments. Returns only NEW actionable decisions.

        Deduplicates against the most recent stored decision per instrument:
        same action + same signal_basis → skip (no change).
        """
        from chanquant.data.decision_store import get_latest_decisions

        # Load latest decisions for dedup
        prev_map: dict[str, dict[str, Any]] = {}
        try:
            prev_list = get_latest_decisions(instruments)
            for p in prev_list:
                prev_map[p["instrument"]] = p
        except Exception:
            pass  # if store unavailable, skip dedup

        decisions: list[TradingDecision] = []
        for inst in instruments:
            try:
                d = self.analyze(inst, macro_news)
                if d is None or d.action == "NO_ACTION":
                    continue
                # Dedup: skip if same action + same signal basis as last decision
                prev = prev_map.get(inst)
                if prev and prev.get("action") == d.action and prev.get("signal_basis") == d.signal_basis:
                    logger.info(f"Skipping duplicate decision for {inst}: {d.action} ({d.signal_basis})")
                    continue
                decisions.append(d)
            except Exception as exc:
                logger.error(f"Decision analysis failed for {inst}: {exc}")
        return decisions

    @staticmethod
    def _is_sell_signal(nesting: dict[str, Any]) -> bool:
        """Check if the dominant signal direction is sell (空)."""
        large = nesting.get("large_signal", "")
        if large and large in ("S1", "S2", "S3"):
            return True
        # If no large signal, check medium/precise
        for key in ("medium_signal", "precise_signal"):
            sig = nesting.get(key, "")
            if sig and sig in ("S1", "S2", "S3"):
                return True
        return False

    def _deterministic_decision(
        self,
        instrument: str,
        nesting: dict[str, Any],
        now: str,
        macro_news: list[dict[str, Any]] | None = None,
        current_price: str = "",
    ) -> TradingDecision | None:
        """Deterministic decision based on nesting + risk manager + strategy params."""
        # Sell signals bypass risk gate — never block an exit
        is_sell = self._is_sell_signal(nesting)

        if not is_sell:
            # Risk manager gate only for BUY signals
            risk_result = self._risk_manager.evaluate(
                nesting_result=nesting,
                params=self._risk,
            )
            if not risk_result.approved:
                logger.info(f"Risk rejected {instrument}: {risk_result.reason}")
                return None

        depth = nesting.get("nesting_depth", 0)
        aligned = nesting.get("direction_aligned", False)
        confidence = float(nesting.get("confidence", 0))

        large_sig = nesting.get("large_signal", "")
        is_buy = large_sig in ("B1", "B2", "B3")

        # Build per-level summary
        per_level = nesting.get("per_level", {})
        level_summary = []
        for tf, info in per_level.items():
            if isinstance(info, dict):
                d = info.get("direction", "—")
                s = info.get("signal", "")
                level_summary.append(f"{tf}: {d or '—'}{f' ({s})' if s else ''}")

        signal_basis = f"大级别: {large_sig}"
        if nesting.get("medium_signal"):
            signal_basis += f", 中级别: {nesting['medium_signal']}"
        if nesting.get("precise_signal"):
            signal_basis += f", 精确: {nesting['precise_signal']}"

        action = "BUY" if is_buy else "SELL"
        urgency = "立即" if depth >= 3 else "等待回调"

        # Summarize macro news
        macro_context = ""
        if macro_news:
            relevant = [
                n for n in macro_news
                if instrument in n.get("tickers", []) or not n.get("tickers")
            ][:5]
            if relevant:
                macro_context = "; ".join(
                    f"[{n.get('source','')}] {n.get('title','')}" for n in relevant
                )
            else:
                macro_context = "; ".join(
                    f"[{n.get('source','')}] {n.get('title','')}" for n in macro_news[:3]
                )

        return TradingDecision(
            instrument=instrument,
            timestamp=now,
            action=action,
            price_current=current_price,
            confidence=confidence,
            urgency=urgency,
            signal_basis=signal_basis,
            macro_context=macro_context,
            reasoning=(
                f"结论：{depth}层级嵌套确认{'做多' if is_buy else '做空'}信号\n"
                f"当前价格：{current_price or '未知'}\n"
                f"依据：{' | '.join(level_summary)}\n"
                f"风险：置信度{confidence*100:.0f}%，"
                f"{'方向一致' if aligned else '方向不一致需警惕'}"
            ),
            nesting_summary=nesting,
        )

    def _llm_decision(
        self,
        instrument: str,
        nesting: dict[str, Any],
        macro_news: list[dict[str, Any]],
        now: str,
        current_price: str = "",
    ) -> TradingDecision | None:
        """LLM-powered decision with macro context.

        Risk manager runs FIRST as a hard gate — if rejected, LLM is never called.
        LLM only makes the final call on risk-approved signals.
        """
        if self._model is None:
            return self._deterministic_decision(instrument, nesting, now, current_price=current_price)

        # Sell signals bypass risk gate — never block an exit
        is_sell = self._is_sell_signal(nesting)
        risk_result = self._risk_manager.evaluate(
            nesting_result=nesting,
            params=self._risk,
        )

        if not is_sell and not risk_result.approved:
            logger.info(f"Risk rejected {instrument} (before LLM): {risk_result.reason}")
            return None

        # Build news context
        news_text = ""
        if macro_news:
            news_items = []
            for n in macro_news[:8]:
                news_items.append(f"- [{n.get('source','')}] {n.get('title','')}")
                if n.get("description"):
                    news_items.append(f"  {n['description']}")
            news_text = "\n".join(news_items)

        nesting_json = json.dumps(nesting, indent=2, default=str, ensure_ascii=False)

        prompt = f"""你是一个专业交易决策Agent。基于以下缠论多级别区间套分析和宏观经济新闻，给出交易决策。

## 区间套分析结果
{nesting_json}

## 近期宏观经济新闻
{news_text if news_text else "无近期重大新闻"}

## 策略参数（用户偏好，供你参考）
- 最小嵌套深度偏好: {self._strategy.min_nesting_depth}
- 最小置信度偏好: {self._strategy.min_confidence}
- 要求方向一致: {"是" if self._strategy.require_alignment else "否"}
- 最小信号强度: {self._strategy.min_signal_strength}
- 允许的信号类型: {', '.join(self._strategy.allowed_signals)}

## 信号质量（供你判断，不是硬规则）
- 嵌套深度: {nesting.get("nesting_depth", 0)} 层
- 方向一致: {"是" if nesting.get("direction_aligned") else "否"}
- 置信度: {nesting.get("confidence", 0)}
- 信号矛盾: {'; '.join(risk_result.conflicts) if risk_result.conflicts else "无"}

## 决策参考
1. 嵌套深度越深越可靠，1层需谨慎，3层以上高确信
2. 方向不一致时需要你综合判断，不是一定不能做
3. 信号矛盾时分析哪个级别更可信（大级别通常优先）
4. 有重大宏观风险事件（如美联储加息、非农数据等）→ 降低仓位或NO_ACTION
5. 综合信号+宏观+用户策略偏好给出 BUY/SELL/NO_ACTION

## 输出JSON格式
```json
{{
  "action": "BUY" 或 "SELL" 或 "NO_ACTION",
  "price_range_low": "建议买入/卖出价格下限",
  "price_range_high": "建议买入/卖出价格上限",
  "stop_loss": "止损价格",
  "position_size": "建议仓位比例，如30%",
  "urgency": "立即" 或 "等待回调" 或 "观察",
  "confidence": 0.0到1.0,
  "signal_basis": "触发信号说明",
  "macro_context": "宏观因素分析",
  "reasoning": "结论：...\\n依据：...\\n风险：..."
}}
```

当前时间: {now}
标的: {instrument}
当前价格: {current_price if current_price else "未知"}

## 风控约束（已通过硬规则检查）
- 建议仓位上限: {risk_result.adjusted_position_pct:.1%}
- 市场环境: {risk_result.regime}
- 回撤状态: {risk_result.drawdown_status}
- position_size 不得超过 {risk_result.adjusted_position_pct:.1%}

重要：价格区间和止损必须基于当前实际价格给出，不要凭空编造价格。

请分析并输出决策JSON："""

        try:
            resp = self._model.invoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            return self._parse_llm_decision(instrument, text, nesting, now, current_price)
        except Exception as exc:
            logger.error(f"LLM decision failed for {instrument}: {exc}")
            return self._deterministic_decision(instrument, nesting, now, current_price=current_price)

    def _parse_llm_decision(
        self,
        instrument: str,
        text: str,
        nesting: dict[str, Any],
        now: str,
        current_price: str = "",
    ) -> TradingDecision | None:
        """Parse LLM JSON response into TradingDecision."""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return self._deterministic_decision(instrument, nesting, now, current_price=current_price)

            raw = json.loads(text[start:end])
            action = raw.get("action", "NO_ACTION").upper()

            if action == "NO_ACTION":
                return None

            return TradingDecision(
                instrument=instrument,
                timestamp=now,
                action=action,
                price_current=current_price,
                price_range_low=str(raw.get("price_range_low", "")),
                price_range_high=str(raw.get("price_range_high", "")),
                stop_loss=str(raw.get("stop_loss", "")),
                position_size=str(raw.get("position_size", "")),
                urgency=str(raw.get("urgency", "")),
                confidence=float(raw.get("confidence", 0)),
                signal_basis=str(raw.get("signal_basis", "")),
                macro_context=str(raw.get("macro_context", "")),
                reasoning=str(raw.get("reasoning", "")),
                nesting_summary=nesting,
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            return self._deterministic_decision(instrument, nesting, now, current_price=current_price)
