"""Tool definitions for Agentic AI agents.

Wraps the core analysis pipeline, data access, and scoring functions
as callable tools that agents can invoke.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from chanquant.core.objects import RawKLine, SignalOutcome, TimeFrame
from chanquant.core.pipeline import AnalysisPipeline


def analyze_instrument(
    klines: Sequence[RawKLine],
    instrument: str = "",
) -> dict[str, Any]:
    """Execute the full L0-L8 deterministic analysis pipeline.

    This is the core tool used by Scanner and Nester agents.

    Returns:
        Dictionary with counts and signal details.
    """
    pipeline = AnalysisPipeline()
    state = None
    for bar in klines:
        state = pipeline.process_bar(bar)
    if state is None:
        return {"error": "no output", "instrument": instrument}

    signals = []
    for sig in state.signals:
        signals.append({
            "signal_type": sig.signal_type.value,
            "level": sig.level.value,
            "instrument": sig.instrument,
            "timestamp": sig.timestamp.isoformat(),
            "price": str(sig.price),
            "strength": str(sig.strength),
            "source_lesson": sig.source_lesson,
            "reasoning": sig.reasoning,
        })

    divergences = []
    for div in state.divergences:
        divergences.append({
            "type": div.type.name,
            "strength": str(div.strength),
            "a_macd_area": str(div.a_macd_area),
            "c_macd_area": str(div.c_macd_area),
            "c_contains_b3": div.c_contains_b3,
        })

    return {
        "instrument": instrument,
        "kline_count": len(state.standard_klines),
        "fractal_count": len(state.fractals),
        "stroke_count": len(state.strokes),
        "segment_count": len(state.segments),
        "center_count": len(state.centers),
        "divergence_count": len(state.divergences),
        "signal_count": len(state.signals),
        "signals": signals,
        "divergences": divergences,
        "trend": state.trend.classification.name if state.trend else None,
    }


def query_signal_outcomes(
    outcomes: Sequence[SignalOutcome],
    signal_type: str | None = None,
    outcome_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Filter and return signal outcomes for review.

    Args:
        outcomes: Full list of tracked outcomes.
        signal_type: Optional filter by signal type (B1/S1/etc).
        outcome_filter: Optional filter by outcome (CORRECT/INCORRECT/etc).
    """
    results: list[dict[str, Any]] = []
    for o in outcomes:
        if signal_type and o.signal_type.value != signal_type:
            continue
        if outcome_filter and o.outcome.name != outcome_filter:
            continue
        results.append({
            "signal_id": o.signal_id,
            "instrument": o.instrument,
            "signal_type": o.signal_type.value,
            "level": o.level.value,
            "signal_price": str(o.signal_price),
            "signal_time": o.signal_time.isoformat(),
            "outcome": o.outcome.name,
            "mfe": str(o.max_favorable_excursion),
            "mae": str(o.max_adverse_excursion),
            "pnl_at_close": str(o.pnl_at_close),
            "bars_to_target": o.bars_to_target,
            "market_regime": o.market_regime.name,
            "vix_at_signal": str(o.vix_at_signal) if o.vix_at_signal else None,
        })
    return results


def score_signals(
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score a batch of signal dicts using the L9 formula.

    Simplified version for agent use — works on dict representations.
    """
    from chanquant.scoring.scorer import _SIGNAL_TYPE_SCORES, _TIMEFRAME_WEIGHTS

    scored = []
    for sig in signals:
        sig_type = sig.get("signal_type", "")
        level = sig.get("level", "")
        strength = Decimal(sig.get("strength", "0.5"))

        type_score = _SIGNAL_TYPE_SCORES.get(sig_type, Decimal("1"))
        tf_weight = Decimal("1")
        for tf in TimeFrame:
            if tf.value == level:
                tf_weight = _TIMEFRAME_WEIGHTS.get(tf, Decimal("1"))
                break

        score = type_score * tf_weight * strength
        scored.append({**sig, "score": str(score)})

    scored.sort(key=lambda x: Decimal(x["score"]), reverse=True)
    return scored
