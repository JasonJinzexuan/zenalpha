"""Signal Outcome tracking for feedback and calibration (v2.1).

Tracks post-signal price behavior over a configurable window,
classifying each signal as CORRECT / INCORRECT / PARTIAL / PENDING.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Sequence
from uuid import uuid4

from chanquant.core.objects import (
    MarketRegime,
    OutcomeType,
    RawKLine,
    Signal,
    SignalOutcome,
    SignalType,
)

_DEFAULT_TRACKING_WINDOW = 20
_MFE_THRESHOLD = Decimal("0.5")  # MFE > 50% of avg center range = CORRECT
_MAE_MFE_RATIO = Decimal("2")    # MAE > 2 * MFE = INCORRECT


def create_outcome(
    signal: Signal,
    market_regime: MarketRegime = MarketRegime.NORMAL,
    vix: Decimal | None = None,
    tracking_window: int = _DEFAULT_TRACKING_WINDOW,
) -> SignalOutcome:
    """Create a pending SignalOutcome to be evaluated later."""
    return SignalOutcome(
        signal_id=uuid4().hex[:16],
        instrument=signal.instrument,
        signal_type=signal.signal_type,
        level=signal.level,
        signal_price=signal.price,
        signal_time=signal.timestamp,
        outcome=OutcomeType.PENDING,
        market_regime=market_regime,
        vix_at_signal=vix,
        tracking_window=tracking_window,
    )


def evaluate_outcome(
    outcome: SignalOutcome,
    subsequent_bars: Sequence[RawKLine],
    avg_center_range: Decimal = Decimal("1"),
) -> SignalOutcome:
    """Evaluate a signal outcome using the bars that followed the signal.

    Args:
        outcome: The pending outcome to evaluate.
        subsequent_bars: K-lines after the signal, up to tracking_window.
        avg_center_range: Average center [ZD,ZG] range at the signal's level,
                          used as reference for MFE threshold.
    """
    if not subsequent_bars:
        return outcome

    is_buy = outcome.signal_type in (SignalType.B1, SignalType.B2, SignalType.B3)
    signal_price = outcome.signal_price

    mfe = Decimal("0")  # max favorable excursion
    mae = Decimal("0")  # max adverse excursion
    bars_to_target: int | None = None
    target_threshold = avg_center_range * _MFE_THRESHOLD

    for i, bar in enumerate(subsequent_bars[: outcome.tracking_window]):
        if is_buy:
            favorable = bar.high - signal_price
            adverse = signal_price - bar.low
        else:
            favorable = signal_price - bar.low
            adverse = bar.high - signal_price

        if favorable > mfe:
            mfe = favorable
        if adverse > mae:
            mae = adverse
        if bars_to_target is None and favorable >= target_threshold:
            bars_to_target = i + 1

    # Last bar PnL
    last_bar = subsequent_bars[min(len(subsequent_bars), outcome.tracking_window) - 1]
    if is_buy:
        pnl = last_bar.close - signal_price
    else:
        pnl = signal_price - last_bar.close

    # Classification
    if len(subsequent_bars) < outcome.tracking_window:
        classification = OutcomeType.PENDING
    elif mfe >= target_threshold:
        classification = OutcomeType.CORRECT
    elif mae > mfe * _MAE_MFE_RATIO:
        classification = OutcomeType.INCORRECT
    else:
        classification = OutcomeType.PARTIAL

    return replace(
        outcome,
        outcome=classification,
        max_favorable_excursion=mfe,
        max_adverse_excursion=mae,
        pnl_at_close=pnl,
        bars_to_target=bars_to_target,
        evaluated_at=datetime.now(),
    )
