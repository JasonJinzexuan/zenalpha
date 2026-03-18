"""Tests for L7 — Signal generation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.objects import (
    Center,
    Direction,
    Divergence,
    DivergenceType,
    Fractal,
    FractalType,
    Segment,
    SignalType,
    StandardKLine,
    Stroke,
    TimeFrame,
    TrendClass,
    TrendType,
)


def _make_segment(direction: Direction, h: str, l: str, macd: str = "50") -> Segment:
    k = StandardKLine(
        datetime(2024, 1, 2), Decimal("100"), Decimal(h), Decimal(l),
        Decimal("100"), 1000,
    )
    f = Fractal(FractalType.TOP, datetime(2024, 1, 2), Decimal(h), 0, (k, k, k))
    s = Stroke(direction, f, f, Decimal(h), Decimal(l), 5,
               macd_area=Decimal(macd),
               start_time=datetime(2024, 1, 2),
               end_time=datetime(2024, 1, 10))
    return Segment(direction, (s,), Decimal(h), Decimal(l), macd_area=Decimal(macd))


def _make_stroke(direction: Direction, h: str, l: str) -> Stroke:
    k = StandardKLine(
        datetime(2024, 1, 2), Decimal("100"), Decimal(h), Decimal(l),
        Decimal("100"), 1000,
    )
    f = Fractal(FractalType.TOP, datetime(2024, 1, 2), Decimal(h), 0, (k, k, k))
    return Stroke(direction, f, f, Decimal(h), Decimal(l), 5,
                  start_time=datetime(2024, 1, 2),
                  end_time=datetime(2024, 1, 10))


def _make_center(zg: str, zd: str) -> Center:
    return Center(level=TimeFrame.DAILY, zg=Decimal(zg), zd=Decimal(zd),
                  gg=Decimal(zg), dd=Decimal(zd))


class TestSignalGenerator:
    def test_imports(self) -> None:
        from chanquant.core.signal import SignalGenerator
        gen = SignalGenerator()
        assert gen is not None

    def test_b1_from_downtrend_divergence(self) -> None:
        from chanquant.core.signal import SignalGenerator

        seg_a = _make_segment(Direction.DOWN, "110", "95", "100")
        seg_c = _make_segment(Direction.DOWN, "100", "88", "60")
        center_a = _make_center("100", "96")
        center_b = _make_center("95", "90")

        trend = TrendType(
            classification=TrendClass.DOWN_TREND,
            centers=(center_a, center_b),
            level=TimeFrame.DAILY,
            segment_a=seg_a,
            center_a=center_a,
            center_b=center_b,
            segment_c=seg_c,
        )
        divergence = Divergence(
            type=DivergenceType.TREND,
            level=TimeFrame.DAILY,
            trend_type=trend,
            segment_a=seg_a,
            segment_c=seg_c,
            a_macd_area=Decimal("100"),
            c_macd_area=Decimal("60"),
            strength=Decimal("0.4"),
        )

        gen = SignalGenerator()
        signals = gen.generate(
            trend=trend,
            divergence=divergence,
            centers=[center_a, center_b],
            segments=[seg_a, seg_c],
            strokes=[_make_stroke(Direction.DOWN, "110", "95")],
            instrument="AAPL",
        )
        b1_signals = [s for s in signals if s.signal_type == SignalType.B1]
        assert len(b1_signals) >= 1

    def test_no_signal_without_divergence(self) -> None:
        from chanquant.core.signal import SignalGenerator

        center = _make_center("108", "98")
        trend = TrendType(
            classification=TrendClass.CONSOLIDATION,
            centers=(center,),
            level=TimeFrame.DAILY,
        )

        gen = SignalGenerator()
        signals = gen.generate(
            trend=trend,
            divergence=None,
            centers=[center],
            segments=[],
            strokes=[],
            instrument="TEST",
        )
        # No divergence, no B3/S3 opportunity → no signals
        b1_s1 = [s for s in signals if s.signal_type in (SignalType.B1, SignalType.S1)]
        assert len(b1_s1) == 0
