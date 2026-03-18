"""ATR-based position sizing, stop loss management, and portfolio constraints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import Direction, Position, RawKLine, SignalType

_RISK_PCT: dict[SignalType, Decimal] = {
    SignalType.B1: Decimal("0.02"),
    SignalType.B2: Decimal("0.015"),
    SignalType.B3: Decimal("0.01"),
    SignalType.S1: Decimal("0.02"),
    SignalType.S2: Decimal("0.015"),
    SignalType.S3: Decimal("0.01"),
}

_BATCH_ALLOCATION: dict[SignalType, Decimal] = {
    SignalType.B1: Decimal("0.5"),
    SignalType.B2: Decimal("0.3"),
    SignalType.B3: Decimal("0.2"),
    SignalType.S1: Decimal("0.5"),
    SignalType.S2: Decimal("0.3"),
    SignalType.S3: Decimal("0.2"),
}

_DEFAULT_MULTIPLIER = Decimal("2.0")
_ATR_PERIOD = 14
_MAX_POSITIONS = 10
_MAX_SINGLE_POSITION_PCT = Decimal("0.15")
_DRAWDOWN_HALF = Decimal("0.10")
_DRAWDOWN_CLEAR = Decimal("0.15")
_TRAILING_ATR_MULT = Decimal("1.5")


def atr(klines: Sequence[RawKLine], period: int = _ATR_PERIOD) -> Decimal:
    """Calculate Average True Range over the given period."""
    if len(klines) < 2:
        return Decimal("0")

    true_ranges: list[Decimal] = []
    for i in range(1, len(klines)):
        prev_close = klines[i - 1].close
        cur = klines[i]
        tr = max(
            cur.high - cur.low,
            abs(cur.high - prev_close),
            abs(cur.low - prev_close),
        )
        true_ranges.append(tr)

    recent = true_ranges[-period:]
    if not recent:
        return Decimal("0")
    return sum(recent, Decimal("0")) / Decimal(str(len(recent)))


class PositionSizer:
    """Calculate position size based on ATR and risk parameters."""

    def __init__(self, multiplier: Decimal = _DEFAULT_MULTIPLIER) -> None:
        self._multiplier = multiplier

    def calculate_size(
        self,
        equity: Decimal,
        atr_value: Decimal,
        signal_type: SignalType,
        risk_pct: Decimal | None = None,
    ) -> Decimal:
        if atr_value <= Decimal("0"):
            return Decimal("0")

        pct = risk_pct or _RISK_PCT.get(signal_type, Decimal("0.01"))
        risk_per_trade = equity * pct
        position_size = risk_per_trade / (atr_value * self._multiplier)
        return position_size

    def calculate_batch_size(
        self,
        equity: Decimal,
        atr_value: Decimal,
        signal_type: SignalType,
        risk_pct: Decimal | None = None,
    ) -> Decimal:
        full_size = self.calculate_size(
            equity, atr_value, signal_type, risk_pct
        )
        alloc = _BATCH_ALLOCATION.get(signal_type, Decimal("0.2"))
        return full_size * alloc

    def check_portfolio_constraints(
        self,
        equity: Decimal,
        position_value: Decimal,
        current_position_count: int,
    ) -> str | None:
        if current_position_count >= _MAX_POSITIONS:
            return "max_positions_reached"
        if equity > Decimal("0"):
            if position_value / equity > _MAX_SINGLE_POSITION_PCT:
                return "single_position_limit_exceeded"
        return None


@dataclass(frozen=True)
class StopResult:
    """Result of a stop loss check."""

    exit_reason: str
    exit_price: Decimal


class StopLossManager:
    """Multi-layer stop loss management."""

    def check_stops(
        self,
        position: Position,
        current_price: Decimal,
        current_time: datetime,
        center_low: Decimal | None = None,
        signal_period: timedelta | None = None,
        atr_value: Decimal | None = None,
        peak_price: Decimal | None = None,
    ) -> str | None:
        hard = self._check_hard_stop(position, current_price, center_low)
        if hard is not None:
            return hard

        time_stop = self._check_time_stop(
            position, current_time, signal_period
        )
        if time_stop is not None:
            return time_stop

        trailing = self._check_trailing_stop(
            position, current_price, atr_value, peak_price
        )
        if trailing is not None:
            return trailing

        return None

    def _check_hard_stop(
        self,
        position: Position,
        current_price: Decimal,
        center_low: Decimal | None,
    ) -> str | None:
        if center_low is None:
            return None
        if position.direction == Direction.UP:
            if current_price < center_low:
                return "hard_stop_below_center"
        else:
            if current_price > center_low:
                return "hard_stop_above_center"
        return None

    def _check_time_stop(
        self,
        position: Position,
        current_time: datetime,
        signal_period: timedelta | None,
    ) -> str | None:
        if signal_period is None:
            return None
        holding_time = current_time - position.entry_time
        max_holding = signal_period * 2
        if holding_time > max_holding:
            return "time_stop_exceeded"
        return None

    def _check_trailing_stop(
        self,
        position: Position,
        current_price: Decimal,
        atr_value: Decimal | None,
        peak_price: Decimal | None,
    ) -> str | None:
        if atr_value is None or peak_price is None:
            return None

        risk_r = abs(position.entry_price - (position.stop_loss or Decimal("0")))
        if risk_r <= Decimal("0"):
            return None

        if position.direction == Direction.UP:
            profit = current_price - position.entry_price
            if profit > risk_r:
                trailing_level = peak_price - atr_value * _TRAILING_ATR_MULT
                if current_price < trailing_level:
                    return "trailing_stop"
        else:
            profit = position.entry_price - current_price
            if profit > risk_r:
                trailing_level = peak_price + atr_value * _TRAILING_ATR_MULT
                if current_price > trailing_level:
                    return "trailing_stop"

        return None


def check_portfolio_drawdown(
    drawdown: Decimal,
) -> str | None:
    """Check portfolio-level drawdown thresholds.

    Returns action to take: 'half_all', 'clear_all', or None.
    """
    if drawdown >= _DRAWDOWN_CLEAR:
        return "clear_all"
    if drawdown >= _DRAWDOWN_HALF:
        return "half_all"
    return None
