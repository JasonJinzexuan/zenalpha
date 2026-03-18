"""Tests for Signal Outcome tracking."""

from datetime import datetime
from decimal import Decimal

from chanquant.core.objects import (
    OutcomeType,
    RawKLine,
    SignalType,
    TimeFrame,
    Signal,
)
from chanquant.scoring.outcome import create_outcome, evaluate_outcome


def _bar(close: str, high: str, low: str, ts: datetime | None = None) -> RawKLine:
    return RawKLine(
        timestamp=ts or datetime(2026, 3, 18),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
    )


def _signal(price: str = "100", signal_type: SignalType = SignalType.B1) -> Signal:
    return Signal(
        signal_type=signal_type,
        level=TimeFrame.DAILY,
        instrument="AAPL",
        timestamp=datetime(2026, 3, 18),
        price=Decimal(price),
    )


class TestCreateOutcome:
    def test_pending_by_default(self):
        outcome = create_outcome(_signal())
        assert outcome.outcome == OutcomeType.PENDING
        assert outcome.instrument == "AAPL"
        assert outcome.signal_type == SignalType.B1


class TestEvaluateOutcome:
    def test_correct_when_mfe_exceeds_threshold(self):
        outcome = create_outcome(_signal("100"), tracking_window=5)
        # Price goes up significantly — MFE = 10
        bars = [_bar("110", "112", "99") for _ in range(5)]
        result = evaluate_outcome(outcome, bars, avg_center_range=Decimal("10"))
        assert result.outcome == OutcomeType.CORRECT
        assert result.max_favorable_excursion >= Decimal("10")

    def test_incorrect_when_mae_dominates(self):
        outcome = create_outcome(_signal("100"), tracking_window=5)
        # Price goes down — MAE much larger than MFE
        bars = [_bar("85", "101", "80") for _ in range(5)]
        result = evaluate_outcome(outcome, bars, avg_center_range=Decimal("10"))
        assert result.outcome == OutcomeType.INCORRECT

    def test_pending_when_window_not_complete(self):
        outcome = create_outcome(_signal("100"), tracking_window=20)
        bars = [_bar("102", "103", "99") for _ in range(5)]  # only 5 of 20
        result = evaluate_outcome(outcome, bars, avg_center_range=Decimal("10"))
        assert result.outcome == OutcomeType.PENDING

    def test_sell_signal_correct_when_price_drops(self):
        outcome = create_outcome(
            _signal("100", SignalType.S1), tracking_window=5
        )
        bars = [_bar("88", "101", "85") for _ in range(5)]
        result = evaluate_outcome(outcome, bars, avg_center_range=Decimal("10"))
        assert result.outcome == OutcomeType.CORRECT
        assert result.pnl_at_close > Decimal("0")
