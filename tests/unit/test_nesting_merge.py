"""Tests for signal merge/dedup logic (rule 8.6)."""

from datetime import datetime
from decimal import Decimal

from chanquant.core.objects import Signal, SignalType, TimeFrame
from chanquant.core.nesting import merge_signals, _dedup_signals


def _sig(
    instrument: str = "AAPL",
    signal_type: SignalType = SignalType.B1,
    level: TimeFrame = TimeFrame.DAILY,
    ts: datetime | None = None,
    strength: Decimal = Decimal("0.8"),
) -> Signal:
    return Signal(
        signal_type=signal_type,
        level=level,
        instrument=instrument,
        timestamp=ts or datetime(2026, 3, 18, 10, 0),
        price=Decimal("150"),
        strength=strength,
    )


class TestMergeSignals:
    def test_single_signal_becomes_primary(self):
        signals = [_sig()]
        merged = merge_signals(signals, "AAPL")
        assert merged is not None
        assert merged.primary_signal.signal_type == SignalType.B1
        assert merged.supporting_signals == ()
        assert merged.nesting_depth == 1

    def test_multi_level_signals_merged(self):
        signals = [
            _sig(level=TimeFrame.WEEKLY, strength=Decimal("0.9")),
            _sig(level=TimeFrame.DAILY, strength=Decimal("0.7")),
            _sig(level=TimeFrame.MIN_30, strength=Decimal("0.5")),
        ]
        merged = merge_signals(signals, "AAPL")
        assert merged is not None
        assert merged.primary_signal.level == TimeFrame.WEEKLY
        assert len(merged.supporting_signals) == 2
        assert merged.nesting_depth == 3

    def test_different_instrument_filtered(self):
        signals = [_sig(instrument="MSFT")]
        merged = merge_signals(signals, "AAPL")
        assert merged is None

    def test_merged_score_is_weighted_sum(self):
        signals = [
            _sig(level=TimeFrame.WEEKLY, strength=Decimal("1")),
            _sig(level=TimeFrame.DAILY, strength=Decimal("1")),
        ]
        merged = merge_signals(signals, "AAPL")
        assert merged is not None
        # weekly weight=5 * 1 + daily weight=3 * 1 = 8
        assert merged.merged_score == Decimal("8")


class TestDedupSignals:
    def test_same_level_same_direction_keeps_latest(self):
        s1 = _sig(ts=datetime(2026, 3, 18, 9, 0))
        s2 = _sig(ts=datetime(2026, 3, 18, 10, 0))
        deduped = _dedup_signals([s1, s2])
        assert len(deduped) == 1
        assert deduped[0].timestamp == s2.timestamp

    def test_different_levels_both_kept(self):
        s1 = _sig(level=TimeFrame.DAILY)
        s2 = _sig(level=TimeFrame.WEEKLY)
        deduped = _dedup_signals([s1, s2])
        assert len(deduped) == 2

    def test_buy_and_sell_same_level_both_kept(self):
        s1 = _sig(signal_type=SignalType.B1)
        s2 = _sig(signal_type=SignalType.S1)
        deduped = _dedup_signals([s1, s2])
        assert len(deduped) == 2
