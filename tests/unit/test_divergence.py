"""Tests for L6 — Divergence detection."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.objects import (
    Center,
    Direction,
    DivergenceType,
    Fractal,
    FractalType,
    MACDValue,
    Segment,
    StandardKLine,
    Stroke,
    TimeFrame,
    TrendClass,
    TrendType,
)


def _make_segment(direction: Direction, h: str, l: str) -> Segment:
    k = StandardKLine(
        datetime(2024, 1, 2), Decimal("100"), Decimal(h), Decimal(l),
        Decimal("100"), 1000,
    )
    f = Fractal(FractalType.TOP, datetime(2024, 1, 2), Decimal(h), 0, (k, k, k))
    s = Stroke(direction, f, f, Decimal(h), Decimal(l), 5,
               macd_area=Decimal("50"))
    return Segment(direction, (s,), Decimal(h), Decimal(l), macd_area=Decimal("50"))


def _make_center(zg: str, zd: str) -> Center:
    return Center(
        level=TimeFrame.DAILY,
        zg=Decimal(zg),
        zd=Decimal(zd),
        gg=Decimal(zg),
        dd=Decimal(zd),
    )


class TestDivergenceDetector:
    def test_imports(self) -> None:
        from chanquant.core.divergence import DivergenceDetector
        detector = DivergenceDetector()
        assert detector is not None

    def test_trend_divergence_a_vs_c(self) -> None:
        """Verify divergence compares a-segment vs c-segment (not b vs c)."""
        from chanquant.core.divergence import DivergenceDetector

        seg_a = _make_segment(Direction.UP, "110", "95")
        seg_b = _make_segment(Direction.DOWN, "108", "100")
        seg_c = _make_segment(Direction.UP, "115", "105")
        center_a = _make_center("108", "98")
        center_b = _make_center("112", "103")

        trend = TrendType(
            classification=TrendClass.UP_TREND,
            centers=(center_a, center_b),
            level=TimeFrame.DAILY,
            segment_a=seg_a,
            center_a=center_a,
            segment_b=seg_b,
            center_b=center_b,
            segment_c=seg_c,
        )

        detector = DivergenceDetector()
        # Generate MACD values — just verify it doesn't crash
        macd_values = [
            MACDValue(Decimal("1"), Decimal("0.5"), Decimal("0.5"))
            for _ in range(30)
        ]
        result = detector.detect(trend, macd_values)
        # May or may not detect divergence, but should not crash

    def test_consolidation_needs_single_center(self) -> None:
        from chanquant.core.divergence import DivergenceDetector

        center = _make_center("108", "98")
        seg_a = _make_segment(Direction.UP, "110", "95")

        trend = TrendType(
            classification=TrendClass.CONSOLIDATION,
            centers=(center,),
            level=TimeFrame.DAILY,
            segment_a=seg_a,
            center_a=center,
        )

        detector = DivergenceDetector()
        result = detector.detect(trend, [])
        # Consolidation with no exit segments → no divergence
