"""L0: K-line containment processing (包含关系处理).

Merges K-lines that have containment relationships based on current direction.
"""

from __future__ import annotations

from chanquant.core.objects import Direction, RawKLine, StandardKLine


def _has_containment(a: StandardKLine, b: StandardKLine) -> bool:
    """Check if a contains b or b contains a."""
    a_contains_b = a.high >= b.high and a.low <= b.low
    b_contains_a = b.high >= a.high and b.low <= a.low
    return a_contains_b or b_contains_a


def _merge(
    a: StandardKLine, b: StandardKLine, direction: Direction
) -> StandardKLine:
    """Merge two K-lines based on current direction."""
    if direction == Direction.UP:
        new_high = max(a.high, b.high)
        new_low = max(a.low, b.low)
    else:
        new_high = min(a.high, b.high)
        new_low = min(a.low, b.low)

    return StandardKLine(
        timestamp=a.timestamp,
        open=a.open,
        high=new_high,
        low=new_low,
        close=b.close,
        volume=a.volume + b.volume,
        original_count=a.original_count + b.original_count,
        direction=direction,
        timeframe=a.timeframe,
    )


def _determine_direction(prev: StandardKLine, curr: StandardKLine) -> Direction:
    """Determine direction by comparing with previous non-contained K-line."""
    if curr.high > prev.high:
        return Direction.UP
    if curr.low < prev.low:
        return Direction.DOWN
    return prev.direction


def _raw_to_standard(raw: RawKLine) -> StandardKLine:
    return StandardKLine(
        timestamp=raw.timestamp,
        open=raw.open,
        high=raw.high,
        low=raw.low,
        close=raw.close,
        volume=raw.volume,
        timeframe=raw.timeframe,
    )


class KLineProcessor:
    """Processes raw K-lines through containment relationship rules.

    Feed raw K-lines one by one. Outputs standardized K-lines after
    containment merging is resolved.
    """

    def __init__(self) -> None:
        self._prev: StandardKLine | None = None
        self._current: StandardKLine | None = None
        self._direction: Direction = Direction.UP
        self._index = 0

    def feed(self, raw: RawKLine) -> StandardKLine | None:
        """Feed a raw K-line. Returns a finalized StandardKLine or None."""
        incoming = _raw_to_standard(raw)

        # First K-line
        if self._current is None:
            self._current = incoming
            return None

        # Check containment between current and incoming
        if _has_containment(self._current, incoming):
            # Determine direction for merge
            if self._prev is not None:
                self._direction = _determine_direction(
                    self._prev, self._current
                )
            # Merge and keep processing (recursive containment)
            self._current = _merge(self._current, incoming, self._direction)
            return None

        # No containment — finalize current, advance
        finalized = self._current
        if self._prev is not None:
            self._direction = _determine_direction(self._prev, finalized)

        self._prev = finalized
        self._current = incoming
        self._index += 1
        return finalized

    def flush(self) -> StandardKLine | None:
        """Flush the last buffered K-line."""
        if self._current is not None:
            result = self._current
            self._current = None
            return result
        return None
