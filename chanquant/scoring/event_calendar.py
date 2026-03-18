"""Event Calendar and Pre/Post Market signal filtering (v2.2).

Handles FOMC, CPI, PPI, OpEx, Quad Witching, and Earnings events.
Also filters signals generated during pre-market / after-hours sessions.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import MarketEvent, Signal, TimeFrame

# ── US market session boundaries (Eastern Time) ─────────────────────────────

_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)

# ── Event-specific adjustment rules ─────────────────────────────────────────
# Each rule: (hours_before, hours_after, score_multiplier_before, score_multiplier_after)

_EVENT_RULES: dict[str, tuple[int, int, Decimal, Decimal]] = {
    "FOMC": (48, 4, Decimal("0.67"), Decimal("0")),  # threshold ×1.5 ≈ score ×0.67
    "CPI": (24, 2, Decimal("0.77"), Decimal("0")),    # threshold ×1.3 ≈ score ×0.77
    "PPI": (24, 2, Decimal("0.77"), Decimal("0")),
    "EARNINGS": (48, 24, Decimal("0"), Decimal("0")),  # basically blocked
    "OPEX": (0, 0, Decimal("1"), Decimal("1")),       # handled per-signal-type below
    "QUAD_WITCHING": (0, 0, Decimal("1"), Decimal("1")),
}


def _is_opex_week(d: date) -> bool:
    """Check if date falls in options expiration week (week of 3rd Friday)."""
    # Find third Friday of the month
    first_day = d.replace(day=1)
    # weekday(): Monday=0 ... Friday=4
    days_to_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_to_friday)
    third_friday = first_friday + timedelta(weeks=2)
    # OpEx week = Monday through Friday of the third Friday's week
    week_start = third_friday - timedelta(days=third_friday.weekday())
    week_end = week_start + timedelta(days=4)
    return week_start <= d <= week_end


def _is_quad_witching_week(d: date) -> bool:
    """Quad witching: 3rd Friday of March, June, September, December."""
    if d.month not in (3, 6, 9, 12):
        return False
    return _is_opex_week(d)


class EventCalendar:
    """Filter and adjust signals based on market events and trading session."""

    def __init__(self, events: Sequence[MarketEvent] = ()) -> None:
        self._events = list(events)

    def add_event(self, event: MarketEvent) -> None:
        self._events.append(event)

    def score_multiplier(
        self,
        signal: Signal,
        current_time: datetime,
    ) -> Decimal:
        """Return a multiplier (0-1) to apply to the signal's score.

        0 = signal blocked, 1 = no adjustment.
        """
        multiplier = Decimal("1")

        # Pre/Post market filtering
        multiplier *= self._session_multiplier(signal, current_time)

        # Event-based filtering
        multiplier *= self._event_multiplier(signal, current_time)

        # OpEx week: block B3/S3 (pin risk)
        multiplier *= self._opex_multiplier(signal, current_time)

        # Quad witching week: block all sub-daily signals
        multiplier *= self._quad_witching_multiplier(signal, current_time)

        return multiplier

    def _session_multiplier(
        self, signal: Signal, current_time: datetime
    ) -> Decimal:
        """Pre/Post market: block 5m/1m signals outside regular hours."""
        if signal.level not in (TimeFrame.MIN_1, TimeFrame.MIN_5):
            return Decimal("1")
        t = current_time.time()
        if _MARKET_OPEN <= t <= _MARKET_CLOSE:
            return Decimal("1")
        return Decimal("0")

    def _event_multiplier(
        self, signal: Signal, current_time: datetime
    ) -> Decimal:
        """Apply event proximity adjustments."""
        result = Decimal("1")
        current_date = current_time.date()

        for event in self._events:
            # Instrument-specific events only affect that instrument
            if event.instrument is not None and event.instrument != signal.instrument:
                continue

            rule = _EVENT_RULES.get(event.event_type)
            if rule is None:
                continue

            hours_before, hours_after, mult_before, mult_after = rule
            event_dt = datetime.combine(event.event_date, time(0, 0))
            delta = (current_time - event_dt).total_seconds() / 3600

            if -hours_before <= delta < 0:
                result = min(result, mult_before)
            elif 0 <= delta <= hours_after:
                result = min(result, mult_after)

        return result

    def _opex_multiplier(
        self, signal: Signal, current_time: datetime
    ) -> Decimal:
        """OpEx week: block B3/S3 signals (pin risk causes false breakouts)."""
        if not _is_opex_week(current_time.date()):
            return Decimal("1")
        from chanquant.core.objects import SignalType
        if signal.signal_type in (SignalType.B3, SignalType.S3):
            return Decimal("0")
        # Other signals get 20% haircut
        return Decimal("0.8")

    def _quad_witching_multiplier(
        self, signal: Signal, current_time: datetime
    ) -> Decimal:
        """Quad witching week: block all sub-daily signals."""
        if not _is_quad_witching_week(current_time.date()):
            return Decimal("1")
        if signal.level in (
            TimeFrame.MIN_1, TimeFrame.MIN_5, TimeFrame.MIN_30, TimeFrame.HOUR_1,
        ):
            return Decimal("0")
        return Decimal("1")
