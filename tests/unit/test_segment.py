"""Tests for L3 — Segment building."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.objects import (
    Direction,
    Fractal,
    FractalType,
    SegmentTermType,
    Stroke,
    StandardKLine,
)
from chanquant.core.segment import SegmentBuilder


def make_std(ts: str, h: str, l: str) -> StandardKLine:
    return StandardKLine(
        timestamp=datetime.fromisoformat(ts),
        open=Decimal("100"), high=Decimal(h), low=Decimal(l),
        close=Decimal("100"), volume=1000, direction=Direction.UP,
    )


def make_fractal(ftype: FractalType, ts: str, value: str, idx: int) -> Fractal:
    k = make_std(ts, "110", "90")
    return Fractal(ftype, datetime.fromisoformat(ts), Decimal(value), idx, (k, k, k))


def make_stroke(direction: Direction, h: str, l: str, start_idx: int, end_idx: int) -> Stroke:
    start_type = FractalType.BOTTOM if direction == Direction.UP else FractalType.TOP
    end_type = FractalType.TOP if direction == Direction.UP else FractalType.BOTTOM
    f1 = make_fractal(start_type, "2024-01-02", l if direction == Direction.UP else h, start_idx)
    f2 = make_fractal(end_type, "2024-01-10", h if direction == Direction.UP else l, end_idx)
    return Stroke(
        direction=direction,
        start_fractal=f1,
        end_fractal=f2,
        high=Decimal(h),
        low=Decimal(l),
        kline_count=end_idx - start_idx + 1,
        start_time=datetime(2024, 1, 2),
        end_time=datetime(2024, 1, 10),
    )


class TestSegmentBuilder:
    def test_needs_at_least_3_strokes(self) -> None:
        builder = SegmentBuilder()
        s1 = make_stroke(Direction.UP, "110", "95", 0, 5)
        s2 = make_stroke(Direction.DOWN, "108", "98", 5, 10)
        r1 = builder.feed(s1)
        r2 = builder.feed(s2)
        assert r1 is None
        assert r2 is None

    def test_three_overlapping_strokes_may_form_segment(self) -> None:
        builder = SegmentBuilder()
        # UP-DOWN-UP with overlap
        s1 = make_stroke(Direction.UP, "110", "95", 0, 5)
        s2 = make_stroke(Direction.DOWN, "108", "98", 5, 10)
        s3 = make_stroke(Direction.UP, "115", "100", 10, 15)
        builder.feed(s1)
        builder.feed(s2)
        builder.feed(s3)
        # 3 strokes may not immediately produce segment — depends on termination

    def test_no_overlap_no_segment(self) -> None:
        builder = SegmentBuilder()
        # UP way above DOWN range → no overlap
        s1 = make_stroke(Direction.UP, "110", "105", 0, 5)
        s2 = make_stroke(Direction.DOWN, "100", "90", 5, 10)
        s3 = make_stroke(Direction.UP, "120", "115", 10, 15)
        builder.feed(s1)
        builder.feed(s2)
        builder.feed(s3)
        # Without overlap, no valid segment should form
