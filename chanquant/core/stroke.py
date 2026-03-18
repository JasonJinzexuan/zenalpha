"""L2: Stroke construction (笔的构建).

Builds strokes from alternating top/bottom fractals with minimum kline distance.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import (
    Direction,
    Fractal,
    FractalType,
    MACDValue,
    Stroke,
)


_MIN_KLINE_GAP = 4  # >=5 klines between fractals (index diff >= 4)


def _fractals_are_valid_pair(start: Fractal, end: Fractal) -> bool:
    """Check if two fractals form a valid stroke pair."""
    if start.type == end.type:
        return False
    if abs(end.kline_index - start.kline_index) < _MIN_KLINE_GAP:
        return False
    return True


def _direction_correct(start: Fractal, end: Fractal) -> bool:
    """Check if the price movement matches the fractal pair direction."""
    if (
        start.type == FractalType.BOTTOM
        and end.type == FractalType.TOP
    ):
        return end.extreme_value > start.extreme_value
    if (
        start.type == FractalType.TOP
        and end.type == FractalType.BOTTOM
    ):
        return end.extreme_value < start.extreme_value
    return False


def _make_stroke(start: Fractal, end: Fractal) -> Stroke:
    """Create a Stroke from two fractals."""
    if start.type == FractalType.BOTTOM:
        direction = Direction.UP
        high = end.extreme_value
        low = start.extreme_value
    else:
        direction = Direction.DOWN
        high = start.extreme_value
        low = end.extreme_value

    kline_count = abs(end.kline_index - start.kline_index) + 1

    return Stroke(
        direction=direction,
        start_fractal=start,
        end_fractal=end,
        high=high,
        low=low,
        kline_count=kline_count,
        start_time=start.timestamp,
        end_time=end.timestamp,
    )


def attach_macd_area(
    stroke: Stroke,
    macd_values: Sequence[MACDValue],
    start_idx: int,
    end_idx: int,
) -> Stroke:
    """Return a new Stroke with MACD area and DIF values attached."""
    if not macd_values or start_idx >= end_idx:
        return stroke

    clamped_start = max(0, start_idx)
    clamped_end = min(len(macd_values), end_idx)

    area = Decimal("0")
    for i in range(clamped_start, clamped_end):
        area += abs(macd_values[i].histogram)

    dif_start = macd_values[clamped_start].dif if clamped_start < len(macd_values) else Decimal("0")
    dif_end = macd_values[clamped_end - 1].dif if clamped_end > 0 else Decimal("0")

    return Stroke(
        direction=stroke.direction,
        start_fractal=stroke.start_fractal,
        end_fractal=stroke.end_fractal,
        high=stroke.high,
        low=stroke.low,
        kline_count=stroke.kline_count,
        macd_area=area,
        macd_dif_start=dif_start,
        macd_dif_end=dif_end,
        start_time=stroke.start_time,
        end_time=stroke.end_time,
    )


class StrokeBuilder:
    """Builds strokes from a stream of fractals.

    Enforces alternation and minimum kline gap rules.
    """

    def __init__(self) -> None:
        self._start_fractal: Fractal | None = None
        self._pending: list[Fractal] = []

    def feed(self, fractal: Fractal) -> Stroke | None:
        """Feed a fractal. Returns a completed Stroke or None."""
        if self._start_fractal is None:
            self._start_fractal = fractal
            return None

        # Check if this fractal can end the current stroke
        if _fractals_are_valid_pair(self._start_fractal, fractal):
            if _direction_correct(self._start_fractal, fractal):
                stroke = _make_stroke(self._start_fractal, fractal)
                self._start_fractal = fractal
                return stroke

        # If same type, update start to more extreme
        if fractal.type == self._start_fractal.type:
            if fractal.type == FractalType.TOP:
                if fractal.extreme_value > self._start_fractal.extreme_value:
                    self._start_fractal = fractal
            else:
                if fractal.extreme_value < self._start_fractal.extreme_value:
                    self._start_fractal = fractal
        else:
            # Opposite type but doesn't meet rules — try as new start
            # Keep the more favorable one
            self._start_fractal = fractal

        return None
