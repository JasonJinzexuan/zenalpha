"""L1: Fractal detection (分型识别).

Detects top and bottom fractals from standardized K-lines with alternation enforcement.
"""

from __future__ import annotations

from chanquant.core.objects import Fractal, FractalType, StandardKLine


def _is_top(a: StandardKLine, b: StandardKLine, c: StandardKLine) -> bool:
    return b.high > a.high and b.high > c.high


def _is_bottom(a: StandardKLine, b: StandardKLine, c: StandardKLine) -> bool:
    return b.low < a.low and b.low < c.low


class FractalDetector:
    """Detects fractals from a stream of StandardKLines.

    Enforces alternation: top must follow bottom and vice versa.
    When duplicates occur, keeps higher top or lower bottom.
    """

    def __init__(self) -> None:
        self._buffer: list[StandardKLine] = []
        self._kline_index = 0
        self._last_fractal: Fractal | None = None

    def feed(self, kline: StandardKLine) -> Fractal | None:
        """Feed a StandardKLine. Returns a Fractal if one is confirmed."""
        self._buffer.append(kline)
        self._kline_index += 1

        if len(self._buffer) < 3:
            return None

        a, b, c = self._buffer[-3], self._buffer[-2], self._buffer[-1]
        idx = self._kline_index - 2  # middle element index

        fractal: Fractal | None = None

        if _is_top(a, b, c):
            candidate = Fractal(
                type=FractalType.TOP,
                timestamp=b.timestamp,
                extreme_value=b.high,
                kline_index=idx,
                elements=(a, b, c),
            )
            fractal = self._apply_alternation(candidate)

        elif _is_bottom(a, b, c):
            candidate = Fractal(
                type=FractalType.BOTTOM,
                timestamp=b.timestamp,
                extreme_value=b.low,
                kline_index=idx,
                elements=(a, b, c),
            )
            fractal = self._apply_alternation(candidate)

        return fractal

    def _apply_alternation(self, candidate: Fractal) -> Fractal | None:
        """Enforce alternation rule. Keep higher top or lower bottom on conflict."""
        if self._last_fractal is None:
            self._last_fractal = candidate
            return candidate

        if candidate.type == self._last_fractal.type:
            # Same type — keep the more extreme one
            if candidate.type == FractalType.TOP:
                if candidate.extreme_value > self._last_fractal.extreme_value:
                    self._last_fractal = candidate
                    return candidate
            else:
                if candidate.extreme_value < self._last_fractal.extreme_value:
                    self._last_fractal = candidate
                    return candidate
            return None

        # Different type — proper alternation
        self._last_fractal = candidate
        return candidate
