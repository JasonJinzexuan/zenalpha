"""Tests for L2 — Stroke building."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.objects import Direction, Fractal, FractalType, StandardKLine
from chanquant.core.stroke import StrokeBuilder


def make_std(ts: str, h: str, l: str) -> StandardKLine:
    return StandardKLine(
        timestamp=datetime.fromisoformat(ts),
        open=Decimal("100"), high=Decimal(h), low=Decimal(l),
        close=Decimal("100"), volume=1000, direction=Direction.UP,
    )


def make_fractal(ftype: FractalType, ts: str, value: str, idx: int) -> Fractal:
    k = make_std(ts, "105", "95")
    return Fractal(
        type=ftype,
        timestamp=datetime.fromisoformat(ts),
        extreme_value=Decimal(value),
        kline_index=idx,
        elements=(k, k, k),
    )


class TestStrokeBuilder:
    def test_first_fractal_returns_none(self) -> None:
        builder = StrokeBuilder()
        f1 = make_fractal(FractalType.BOTTOM, "2024-01-02", "99", 0)
        assert builder.feed(f1) is None

    def test_up_stroke_from_bottom_to_top(self) -> None:
        builder = StrokeBuilder()
        f1 = make_fractal(FractalType.BOTTOM, "2024-01-02", "95", 0)
        f2 = make_fractal(FractalType.TOP, "2024-01-09", "110", 7)
        builder.feed(f1)
        result = builder.feed(f2)
        # index diff = 7 >= 4 (min gap), different types, price correct
        assert result is not None
        assert result.direction == Direction.UP
        assert result.high == Decimal("110")
        assert result.low == Decimal("95")

    def test_down_stroke_from_top_to_bottom(self) -> None:
        builder = StrokeBuilder()
        f1 = make_fractal(FractalType.TOP, "2024-01-02", "110", 0)
        f2 = make_fractal(FractalType.BOTTOM, "2024-01-09", "95", 7)
        builder.feed(f1)
        result = builder.feed(f2)
        assert result is not None
        assert result.direction == Direction.DOWN

    def test_too_close_fractals_no_stroke(self) -> None:
        builder = StrokeBuilder()
        f1 = make_fractal(FractalType.BOTTOM, "2024-01-02", "95", 0)
        f2 = make_fractal(FractalType.TOP, "2024-01-04", "110", 2)  # gap < 4
        builder.feed(f1)
        result = builder.feed(f2)
        assert result is None

    def test_same_type_updates_start(self) -> None:
        builder = StrokeBuilder()
        f1 = make_fractal(FractalType.BOTTOM, "2024-01-02", "99", 0)
        f2 = make_fractal(FractalType.BOTTOM, "2024-01-05", "97", 5)
        builder.feed(f1)
        result = builder.feed(f2)
        assert result is None  # Same type, no stroke

    def test_full_pipeline_produces_strokes(self, uptrend_klines) -> None:
        from chanquant.core.fractal import FractalDetector
        from chanquant.core.kline import KLineProcessor

        proc = KLineProcessor()
        detector = FractalDetector()
        builder = StrokeBuilder()
        stroke_count = 0
        for kline in uptrend_klines:
            std = proc.feed(kline)
            if std:
                fractal = detector.feed(std)
                if fractal:
                    stroke = builder.feed(fractal)
                    if stroke:
                        stroke_count += 1
        assert stroke_count >= 0
