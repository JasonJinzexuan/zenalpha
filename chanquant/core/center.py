"""L4: Center (中枢) detection.

Detects, extends, and manages pivot zones from overlapping segments.
"""

from __future__ import annotations

from decimal import Decimal

from chanquant.core.objects import Center, Segment, TimeFrame


def _segments_overlap(a: Segment, b: Segment) -> tuple[Decimal, Decimal] | None:
    """Check if two segments overlap. Returns (zg, zd) if they do."""
    zg = min(a.high, b.high)
    zd = max(a.low, b.low)
    if zg > zd:
        return zg, zd
    return None


def _segment_overlaps_range(seg: Segment, zd: Decimal, zg: Decimal) -> bool:
    """Check if a segment overlaps the [ZD, ZG] range."""
    return seg.high > zd and seg.low < zg


def _centers_overlap_gg_dd(a: Center, b: Center) -> bool:
    """Check if two centers' [DD, GG] ranges overlap (expansion rule)."""
    return a.gg > b.dd and b.gg > a.dd


def _make_center(
    segments: list[Segment],
    zg: Decimal,
    zd: Decimal,
    level: TimeFrame,
) -> Center:
    gg = max(s.high for s in segments)
    dd = min(s.low for s in segments)
    return Center(
        level=level,
        zg=zg,
        zd=zd,
        gg=gg,
        dd=dd,
        segments=tuple(segments),
        start_time=segments[0].start_time,
        end_time=segments[-1].end_time,
        extension_count=max(0, len(segments) - 3),
    )


def _extend_center(center: Center, segment: Segment) -> Center:
    """Return a new center with the segment added (extension)."""
    new_segments = center.segments + (segment,)
    new_gg = max(center.gg, segment.high)
    new_dd = min(center.dd, segment.low)
    return Center(
        level=center.level,
        zg=center.zg,
        zd=center.zd,
        gg=new_gg,
        dd=new_dd,
        segments=new_segments,
        start_time=center.start_time,
        end_time=segment.end_time,
        extension_count=center.extension_count + 1,
    )


def expand_centers(a: Center, b: Center) -> Center | None:
    """Try to merge two same-level centers with overlapping [DD,GG] ranges."""
    if a.level != b.level:
        return None
    if not _centers_overlap_gg_dd(a, b):
        return None

    all_segments = a.segments + b.segments
    new_zg = min(a.zg, b.zg)
    new_zd = max(a.zd, b.zd)
    if new_zg <= new_zd:
        # Expanded range invalid — use wider bounds
        new_zg = max(a.zg, b.zg)
        new_zd = min(a.zd, b.zd)

    return _make_center(list(all_segments), new_zg, new_zd, a.level)


class CenterDetector:
    """Detects centers (中枢) from a stream of segments."""

    def __init__(self, level: TimeFrame = TimeFrame.DAILY) -> None:
        self._level = level
        self._buffer: list[Segment] = []
        self._current: Center | None = None
        self._completed: list[Center] = []

    @property
    def active_center(self) -> Center | None:
        """Return the in-progress center (not yet broken out)."""
        return self._current

    def feed(self, segment: Segment) -> Center | None:
        """Feed a segment. Returns a completed Center or None."""
        # If we have an active center, try to extend or break
        if self._current is not None:
            return self._handle_active_center(segment)

        # Accumulate segments for initial center formation
        self._buffer.append(segment)
        if len(self._buffer) < 3:
            return None

        return self._try_form_center()

    def _try_form_center(self) -> Center | None:
        """Try to form a center from the first 3 buffered segments."""
        if len(self._buffer) < 3:
            return None

        s1, s2 = self._buffer[0], self._buffer[1]
        overlap = _segments_overlap(s1, s2)
        if overlap is None:
            # No overlap between first two — slide window
            self._buffer.pop(0)
            return self._try_form_center()

        zg, zd = overlap

        # Check if third segment overlaps
        s3 = self._buffer[2]
        if _segment_overlaps_range(s3, zd, zg):
            self._current = _make_center(
                list(self._buffer[:3]), zg, zd, self._level
            )
            self._buffer.clear()
            return None

        # Third doesn't overlap — slide
        self._buffer.pop(0)
        return self._try_form_center()

    def _handle_active_center(self, segment: Segment) -> Center | None:
        """Handle a new segment when we have an active center."""
        assert self._current is not None

        if _segment_overlaps_range(segment, self._current.zd, self._current.zg):
            # Extension: segment overlaps [ZD, ZG]
            self._current = _extend_center(self._current, segment)
            return None

        # Segment breaks out — current center is complete
        completed = self._current
        self._completed.append(completed)

        self._current = None
        self._buffer = [segment]
        return completed
