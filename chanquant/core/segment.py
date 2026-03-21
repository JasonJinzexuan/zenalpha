"""L3: Segment construction (线段构建).

Builds segments from strokes using characteristic sequence analysis.
Most complex component — handles first-kind and second-kind termination.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from chanquant.core.objects import (
    Direction,
    Segment,
    SegmentTermType,
    Stroke,
)


# ── Characteristic Sequence Element ─────────────────────────────────────────


@dataclass(frozen=True)
class _CharElement:
    """An element in the characteristic sequence (特征序列)."""

    high: Decimal
    low: Decimal
    stroke: Stroke
    index: int


# ── Helpers ─────────────────────────────────────────────────────────────────


def _build_char_sequence(
    strokes: list[Stroke], seg_direction: Direction
) -> list[_CharElement]:
    """Build characteristic sequence from counter-direction strokes."""
    elements: list[_CharElement] = []
    for i, s in enumerate(strokes):
        if s.direction != seg_direction:
            elements.append(_CharElement(high=s.high, low=s.low, stroke=s, index=i))
    return elements


def _char_containment(a: _CharElement, b: _CharElement) -> bool:
    return (a.high >= b.high and a.low <= b.low) or (
        b.high >= a.high and b.low <= a.low
    )


def _merge_char_elements(
    a: _CharElement, b: _CharElement, direction: Direction
) -> _CharElement:
    """Merge two characteristic elements using containment rules."""
    if direction == Direction.UP:
        return _CharElement(
            high=max(a.high, b.high),
            low=max(a.low, b.low),
            stroke=a.stroke,
            index=a.index,
        )
    return _CharElement(
        high=min(a.high, b.high),
        low=min(a.low, b.low),
        stroke=a.stroke,
        index=a.index,
    )


def _standardize_char_sequence(
    elements: list[_CharElement], direction: Direction
) -> list[_CharElement]:
    """Apply containment processing to characteristic sequence."""
    if len(elements) < 2:
        return list(elements)

    result: list[_CharElement] = [elements[0]]
    for elem in elements[1:]:
        if _char_containment(result[-1], elem):
            merged = _merge_char_elements(result[-1], elem, direction)
            result[-1] = merged
        else:
            result.append(elem)
    return result


def _has_char_top_fractal(a: _CharElement, b: _CharElement, c: _CharElement) -> bool:
    return b.high > a.high and b.high > c.high


def _has_char_bottom_fractal(
    a: _CharElement, b: _CharElement, c: _CharElement
) -> bool:
    return b.low < a.low and b.low < c.low


def _has_gap(
    elem1: _CharElement, elem2: _CharElement, direction: Direction
) -> bool:
    """Check if there is a gap between two characteristic elements.

    For up segment: gap exists if elem1.low > elem2.high.
    For down segment: gap exists if elem1.high < elem2.low.
    """
    if direction == Direction.UP:
        return elem1.low > elem2.high
    return elem1.high < elem2.low


def _calc_segment_macd_area(strokes: tuple[Stroke, ...]) -> Decimal:
    total = Decimal("0")
    for s in strokes:
        total += abs(s.macd_area)
    return total


def _make_segment(
    strokes: list[Stroke],
    direction: Direction,
    term_type: SegmentTermType,
) -> Segment:
    stroke_tuple = tuple(strokes)
    high = max(s.high for s in strokes)
    low = min(s.low for s in strokes)

    # Determine actual direction from price movement, not from
    # the characteristic sequence termination direction.
    first_price = strokes[0].low if strokes[0].direction == Direction.UP else strokes[0].high
    last_price = strokes[-1].high if strokes[-1].direction == Direction.UP else strokes[-1].low
    actual_direction = Direction.UP if last_price > first_price else Direction.DOWN

    return Segment(
        direction=actual_direction,
        strokes=stroke_tuple,
        high=high,
        low=low,
        termination_type=term_type,
        macd_area=_calc_segment_macd_area(stroke_tuple),
    )


# ── First-Kind Termination ──────────────────────────────────────────────────


def _check_first_kind(
    std_chars: list[_CharElement], seg_direction: Direction
) -> bool:
    """First kind: fractal in characteristic sequence, no gap between elem 1&2."""
    if len(std_chars) < 3:
        return False

    for i in range(1, len(std_chars) - 1):
        a, b, c = std_chars[i - 1], std_chars[i], std_chars[i + 1]
        has_fractal = False
        if seg_direction == Direction.UP:
            has_fractal = _has_char_top_fractal(a, b, c)
        else:
            has_fractal = _has_char_bottom_fractal(a, b, c)

        if has_fractal and not _has_gap(std_chars[0], std_chars[1], seg_direction):
            return True
    return False


# ── Second-Kind Termination ─────────────────────────────────────────────────


def _check_second_kind(
    std_chars: list[_CharElement],
    strokes: list[Stroke],
    seg_direction: Direction,
) -> bool:
    """Second kind: gap between elem 1&2, reverse sequence has fractal."""
    if len(std_chars) < 2:
        return False

    if not _has_gap(std_chars[0], std_chars[1], seg_direction):
        return False

    # Build reverse characteristic sequence (same-direction strokes)
    reverse_dir = (
        Direction.DOWN if seg_direction == Direction.UP else Direction.UP
    )
    reverse_elements = _build_char_sequence(strokes, reverse_dir)
    reverse_std = _standardize_char_sequence(reverse_elements, reverse_dir)

    if len(reverse_std) < 3:
        return False

    for i in range(1, len(reverse_std) - 1):
        a, b, c = reverse_std[i - 1], reverse_std[i], reverse_std[i + 1]
        if reverse_dir == Direction.UP:
            if _has_char_bottom_fractal(a, b, c):
                return True
        else:
            if _has_char_top_fractal(a, b, c):
                return True
    return False


# ── Segment Builder ─────────────────────────────────────────────────────────


class SegmentBuilder:
    """Builds segments from a stream of strokes.

    Uses characteristic sequence analysis for segment termination detection.
    """

    def __init__(self) -> None:
        self._strokes: list[Stroke] = []
        self._direction: Direction | None = None

    def feed(self, stroke: Stroke) -> Segment | None:
        """Feed a stroke. Returns a completed Segment or None."""
        self._strokes.append(stroke)

        # Need at least 3 strokes to form a segment
        if len(self._strokes) < 3:
            if self._direction is None and len(self._strokes) == 1:
                self._direction = stroke.direction
            return None

        # Set initial direction from first stroke
        if self._direction is None:
            self._direction = self._strokes[0].direction

        # Only check termination when we have enough strokes
        # and the latest stroke could end the segment
        return self._try_terminate()

    def _try_terminate(self) -> Segment | None:
        """Attempt to detect segment termination.

        Checks both the current direction and the opposite direction,
        since the initial direction may not match the actual segment trend.
        """
        if self._direction is None or len(self._strokes) < 3:
            return None

        # Check current direction first
        result = self._check_direction(self._direction)
        if result is not None:
            return result

        # Also check opposite direction
        opposite = Direction.DOWN if self._direction == Direction.UP else Direction.UP
        result = self._check_direction(opposite)
        if result is not None:
            return result

        return None

    def _check_direction(self, direction: Direction) -> Segment | None:
        """Check for segment termination in the given direction."""
        char_seq = _build_char_sequence(self._strokes, direction)
        std_chars = _standardize_char_sequence(char_seq, direction)

        if _check_first_kind(std_chars, direction):
            self._direction = direction
            return self._finalize_segment(SegmentTermType.FIRST_KIND)

        if _check_second_kind(std_chars, self._strokes, direction):
            self._direction = direction
            return self._finalize_segment(SegmentTermType.SECOND_KIND)

        return None

    def _finalize_segment(self, term_type: SegmentTermType) -> Segment:
        """Create segment and reset state for next segment."""
        segment = _make_segment(self._strokes, self._direction, term_type)  # type: ignore[arg-type]

        # The last stroke becomes the start of the next potential segment
        last = self._strokes[-1]
        self._strokes = [last]
        self._direction = last.direction

        return segment
