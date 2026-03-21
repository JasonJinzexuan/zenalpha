"""L5: Trend classification (走势类型).

Classifies market state based on center relationships.
"""

from __future__ import annotations

from typing import Sequence

from chanquant.core.objects import (
    Center,
    Direction,
    Segment,
    TimeFrame,
    TrendClass,
    TrendType,
)


def _centers_non_overlapping_up(a: Center, b: Center) -> bool:
    """Two centers are non-overlapping upward: b's ZD > a's ZG."""
    return b.zd > a.zg


def _centers_non_overlapping_down(a: Center, b: Center) -> bool:
    """Two centers are non-overlapping downward: b's ZG < a's ZD."""
    return b.zg < a.zd


def _find_segment_between(
    segments: Sequence[Segment],
    center_a: Center,
    center_b: Center,
) -> Segment | None:
    """Find the connecting segment between two centers (segment b).

    Centers often share boundary segments, so we relax the strict time
    containment and look for a segment that overlaps the gap region.
    """
    if not center_a.end_time or not center_b.start_time:
        return None

    # Strict: segment fully between centers
    for seg in segments:
        if seg.start_time and seg.end_time:
            if seg.start_time >= center_a.end_time and seg.end_time <= center_b.start_time:
                return seg

    # Relaxed: segment that spans the boundary (starts near a's end, ends near b's start)
    for seg in segments:
        if seg.start_time and seg.end_time:
            overlaps_a_end = seg.end_time >= center_a.end_time
            overlaps_b_start = seg.start_time <= center_b.start_time
            mostly_between = seg.start_time >= center_a.start_time and seg.end_time <= center_b.end_time
            if overlaps_a_end and overlaps_b_start and mostly_between:
                return seg
    return None


def _find_exit_segment(
    segments: Sequence[Segment],
    center: Center,
    direction: Direction,
) -> Segment | None:
    """Find the exit segment after a center (segment c or a)."""
    if not center.end_time:
        return None
    for seg in segments:
        if seg.start_time and seg.start_time >= center.end_time:
            if seg.direction == direction:
                return seg
    return None


def _find_entry_segment(
    segments: Sequence[Segment],
    center: Center,
    direction: Direction,
) -> Segment | None:
    """Find the entry segment before a center (segment a)."""
    if not center.start_time:
        return None
    for seg in reversed(segments):
        if seg.end_time and seg.end_time <= center.start_time:
            if seg.direction == direction:
                return seg
    return None


class TrendClassifier:
    """Classifies the current market trend from centers and segments."""

    def classify(
        self,
        centers: Sequence[Center],
        segments: Sequence[Segment],
        level: TimeFrame = TimeFrame.DAILY,
    ) -> TrendType:
        """Classify the trend type based on center relationships.

        Uses a sliding window over the most recent centers to detect local
        trends, rather than requiring ALL centers to be non-overlapping.
        """
        if not centers:
            return TrendType(
                classification=TrendClass.CONSOLIDATION,
                centers=(),
                level=level,
            )

        if len(centers) == 1:
            return self._classify_consolidation(centers[0], segments, level)

        # Check recent centers (last 2-3) for local trend
        recent = centers[-3:] if len(centers) >= 3 else centers[-2:]

        # Check for up trend in recent window
        if self._is_up_trend(recent):
            return self._build_trend(
                TrendClass.UP_TREND, centers, segments, level, Direction.UP
            )

        # Check for down trend in recent window
        if self._is_down_trend(recent):
            return self._build_trend(
                TrendClass.DOWN_TREND, centers, segments, level, Direction.DOWN
            )

        # Pairwise check: even if 3 centers don't all agree,
        # the last 2 may indicate a local trend
        if len(recent) > 2:
            last_two = recent[-2:]
            if self._is_up_trend(last_two):
                return self._build_trend(
                    TrendClass.UP_TREND, centers, segments, level, Direction.UP
                )
            if self._is_down_trend(last_two):
                return self._build_trend(
                    TrendClass.DOWN_TREND, centers, segments, level, Direction.DOWN
                )

        # Default: consolidation with the latest center
        return self._classify_consolidation(centers[-1], segments, level)

    def _is_up_trend(self, centers: Sequence[Center]) -> bool:
        for i in range(len(centers) - 1):
            if not _centers_non_overlapping_up(centers[i], centers[i + 1]):
                return False
        return True

    def _is_down_trend(self, centers: Sequence[Center]) -> bool:
        for i in range(len(centers) - 1):
            if not _centers_non_overlapping_down(centers[i], centers[i + 1]):
                return False
        return True

    def _classify_consolidation(
        self,
        center: Center,
        segments: Sequence[Segment],
        level: TimeFrame,
    ) -> TrendType:
        return TrendType(
            classification=TrendClass.CONSOLIDATION,
            centers=(center,),
            level=level,
            center_a=center,
        )

    def _build_trend(
        self,
        classification: TrendClass,
        centers: Sequence[Center],
        segments: Sequence[Segment],
        level: TimeFrame,
        direction: Direction,
    ) -> TrendType:
        """Build a+A+b+B+c trend structure."""
        center_a = centers[-2] if len(centers) >= 2 else None
        center_b = centers[-1]

        seg_a = (
            _find_entry_segment(segments, center_a, direction)
            if center_a
            else None
        )
        seg_b = (
            _find_segment_between(segments, center_a, center_b)
            if center_a
            else None
        )
        seg_c = _find_exit_segment(segments, center_b, direction)

        return TrendType(
            classification=classification,
            centers=tuple(centers),
            level=level,
            segment_a=seg_a,
            center_a=center_a,
            segment_b=seg_b,
            center_b=center_b,
            segment_c=seg_c,
        )
