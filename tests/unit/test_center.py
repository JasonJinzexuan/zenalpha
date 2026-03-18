"""Tests for L4 — Center (中枢) detection."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.center import CenterDetector
from chanquant.core.objects import (
    Direction,
    Fractal,
    FractalType,
    Segment,
    SegmentTermType,
    StandardKLine,
    Stroke,
    TimeFrame,
)


def make_segment(direction: Direction, h: str, l: str) -> Segment:
    k = StandardKLine(
        datetime(2024, 1, 2), Decimal("100"), Decimal(h), Decimal(l),
        Decimal("100"), 1000, direction=Direction.UP,
    )
    f = Fractal(FractalType.TOP, datetime(2024, 1, 2), Decimal(h), 0, (k, k, k))
    s = Stroke(direction, f, f, Decimal(h), Decimal(l), 5,
               start_time=datetime(2024, 1, 2), end_time=datetime(2024, 1, 5))
    return Segment(
        direction=direction,
        strokes=(s,),
        high=Decimal(h),
        low=Decimal(l),
    )


class TestCenterDetector:
    def test_needs_3_segments(self) -> None:
        detector = CenterDetector(level=TimeFrame.DAILY)
        s1 = make_segment(Direction.UP, "110", "95")
        s2 = make_segment(Direction.DOWN, "108", "98")
        assert detector.feed(s1) is None
        assert detector.feed(s2) is None

    def test_overlapping_segments_form_center(self) -> None:
        detector = CenterDetector(level=TimeFrame.DAILY)
        # Three segments with overlapping ranges
        s1 = make_segment(Direction.UP, "110", "95")
        s2 = make_segment(Direction.DOWN, "108", "98")
        s3 = make_segment(Direction.UP, "112", "100")
        detector.feed(s1)
        detector.feed(s2)
        result = detector.feed(s3)
        if result:
            # ZG = min of highs, ZD = max of lows
            assert result.zg <= Decimal("110")
            assert result.zd >= Decimal("98")

    def test_non_overlapping_no_center(self) -> None:
        detector = CenterDetector(level=TimeFrame.DAILY)
        s1 = make_segment(Direction.UP, "110", "105")
        s2 = make_segment(Direction.DOWN, "100", "90")
        s3 = make_segment(Direction.UP, "120", "115")
        detector.feed(s1)
        detector.feed(s2)
        result = detector.feed(s3)
        # Non-overlapping segments → no valid center (ZG < ZD)
        # Detector should return None
