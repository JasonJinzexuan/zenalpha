"""Tests for Event Calendar and Pre/Post Market filtering."""

from datetime import date, datetime, time
from decimal import Decimal

from chanquant.core.objects import (
    EventImpact,
    MarketEvent,
    Signal,
    SignalType,
    TimeFrame,
)
from chanquant.scoring.event_calendar import (
    EventCalendar,
    _is_opex_week,
    _is_quad_witching_week,
)


def _make_signal(
    level: TimeFrame = TimeFrame.DAILY,
    signal_type: SignalType = SignalType.B1,
    instrument: str = "AAPL",
) -> Signal:
    return Signal(
        signal_type=signal_type,
        level=level,
        instrument=instrument,
        timestamp=datetime(2026, 3, 18, 10, 30),
        price=Decimal("150"),
    )


class TestPrePostMarket:
    def test_5m_signal_blocked_premarket(self):
        cal = EventCalendar()
        sig = _make_signal(level=TimeFrame.MIN_5)
        # 8:00 AM ET = pre-market, use non-opex date
        t = datetime(2026, 3, 2, 8, 0)
        assert cal.score_multiplier(sig, t) == Decimal("0")

    def test_5m_signal_allowed_during_market(self):
        cal = EventCalendar()
        sig = _make_signal(level=TimeFrame.MIN_5)
        # Use a date that is NOT in OpEx/Quad Witching week
        t = datetime(2026, 3, 2, 10, 30)
        assert cal.score_multiplier(sig, t) == Decimal("1")

    def test_daily_signal_unaffected_premarket(self):
        cal = EventCalendar()
        sig = _make_signal(level=TimeFrame.DAILY)
        t = datetime(2026, 3, 2, 7, 0)
        assert cal.score_multiplier(sig, t) == Decimal("1")


class TestEventFiltering:
    def test_fomc_before_event_reduces_score(self):
        cal = EventCalendar(
            events=[
                MarketEvent(
                    event_type="FOMC",
                    event_date=date(2026, 4, 10),
                )
            ]
        )
        sig = _make_signal()
        # 24h before FOMC (within 48h window)
        t = datetime(2026, 4, 9, 10, 0)
        mult = cal.score_multiplier(sig, t)
        assert mult < Decimal("1")

    def test_earnings_blocks_signal(self):
        cal = EventCalendar(
            events=[
                MarketEvent(
                    event_type="EARNINGS",
                    event_date=date(2026, 4, 10),
                    instrument="AAPL",
                )
            ]
        )
        sig = _make_signal(instrument="AAPL")
        t = datetime(2026, 4, 9, 10, 0)  # 14h before
        mult = cal.score_multiplier(sig, t)
        assert mult == Decimal("0")

    def test_earnings_different_instrument_not_affected(self):
        cal = EventCalendar(
            events=[
                MarketEvent(
                    event_type="EARNINGS",
                    event_date=date(2026, 4, 10),
                    instrument="AAPL",
                )
            ]
        )
        sig = _make_signal(instrument="MSFT")
        t = datetime(2026, 4, 9, 10, 0)
        mult = cal.score_multiplier(sig, t)
        assert mult == Decimal("1")


class TestOpExWeek:
    def test_third_friday_is_opex(self):
        # March 2026: 3rd Friday = March 20
        assert _is_opex_week(date(2026, 3, 20))

    def test_first_week_not_opex(self):
        assert not _is_opex_week(date(2026, 3, 2))

    def test_b3_blocked_during_opex(self):
        cal = EventCalendar()
        sig = _make_signal(signal_type=SignalType.B3)
        # 2026-03-20 is a Friday in opex week
        t = datetime(2026, 3, 20, 11, 0)
        mult = cal.score_multiplier(sig, t)
        assert mult == Decimal("0")


class TestQuadWitching:
    def test_march_quad_witching(self):
        # March 2026 3rd Friday
        assert _is_quad_witching_week(date(2026, 3, 20))

    def test_february_not_quad_witching(self):
        assert not _is_quad_witching_week(date(2026, 2, 20))

    def test_intraday_blocked_during_quad_witching(self):
        cal = EventCalendar()
        sig = _make_signal(level=TimeFrame.MIN_30)
        t = datetime(2026, 3, 20, 11, 0)
        mult = cal.score_multiplier(sig, t)
        assert mult == Decimal("0")
