"""MACD indicator with incremental EMA calculation.

Uses float internally for EMA performance, converts output to Decimal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import MACDValue


class IncrementalMACD:
    """Incremental MACD calculator using exponential moving averages."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> None:
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._signal_period = signal_period
        self._fast_multiplier = 2.0 / (fast_period + 1)
        self._slow_multiplier = 2.0 / (slow_period + 1)
        self._signal_multiplier = 2.0 / (signal_period + 1)
        self._fast_ema: float | None = None
        self._slow_ema: float | None = None
        self._signal_ema: float | None = None
        self._count = 0
        self._fast_sum = 0.0
        self._slow_sum = 0.0

    def feed(self, close_price: Decimal) -> MACDValue:
        """Feed a close price and return the current MACD values."""
        price = float(close_price)
        self._count += 1

        if self._count <= self._fast_period:
            self._fast_sum += price
        if self._count <= self._slow_period:
            self._slow_sum += price

        # Bootstrap fast EMA
        if self._count == self._fast_period:
            self._fast_ema = self._fast_sum / self._fast_period
        elif self._fast_ema is not None:
            self._fast_ema = (
                price * self._fast_multiplier
                + self._fast_ema * (1.0 - self._fast_multiplier)
            )

        # Bootstrap slow EMA
        if self._count == self._slow_period:
            self._slow_ema = self._slow_sum / self._slow_period
        elif self._slow_ema is not None:
            self._slow_ema = (
                price * self._slow_multiplier
                + self._slow_ema * (1.0 - self._slow_multiplier)
            )

        if self._fast_ema is None or self._slow_ema is None:
            return MACDValue()

        dif = self._fast_ema - self._slow_ema

        if self._signal_ema is None:
            self._signal_ema = dif
        else:
            self._signal_ema = (
                dif * self._signal_multiplier
                + self._signal_ema * (1.0 - self._signal_multiplier)
            )

        dea = self._signal_ema
        histogram = 2.0 * (dif - dea)

        return MACDValue(
            dif=Decimal(str(round(dif, 8))),
            dea=Decimal(str(round(dea, 8))),
            histogram=Decimal(str(round(histogram, 8))),
        )


def macd_area(values: Sequence[MACDValue], start: int, end: int) -> Decimal:
    """Calculate the absolute sum of MACD histogram in [start, end) range."""
    if not values or start >= end:
        return Decimal("0")
    clamped_start = max(0, start)
    clamped_end = min(len(values), end)
    total = Decimal("0")
    for i in range(clamped_start, clamped_end):
        total += abs(values[i].histogram)
    return total
