"""Tests for core data structures — immutability and construction."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
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
    MACDValue,
    MarketRegime,
    PipelineState,
    RawKLine,
    ScanResult,
    Segment,
    SegmentTermType,
    Signal,
    SignalType,
    StandardKLine,
    Stroke,
    TimeFrame,
    TrendClass,
    TrendType,
)


class TestEnums:
    def test_direction_values(self) -> None:
        assert Direction.UP != Direction.DOWN

    def test_fractal_type_values(self) -> None:
        assert FractalType.TOP != FractalType.BOTTOM

    def test_timeframe_values(self) -> None:
        assert TimeFrame.DAILY.value == "1d"
        assert TimeFrame.WEEKLY.value == "1w"
        assert TimeFrame.MIN_5.value == "5m"

    def test_signal_type_values(self) -> None:
        assert SignalType.B1.value == "B1"
        assert SignalType.S3.value == "S3"

    def test_trend_class(self) -> None:
        assert TrendClass.UP_TREND != TrendClass.CONSOLIDATION

    def test_segment_term_type(self) -> None:
        assert SegmentTermType.FIRST_KIND != SegmentTermType.SECOND_KIND

    def test_market_regime(self) -> None:
        assert MarketRegime.EXTREME != MarketRegime.NORMAL


class TestRawKLine:
    def test_create(self) -> None:
        kline = RawKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100.5"),
            high=Decimal("102.0"),
            low=Decimal("99.0"),
            close=Decimal("101.5"),
            volume=1000000,
        )
        assert kline.high == Decimal("102.0")
        assert kline.volume == 1000000
        assert kline.timeframe == TimeFrame.DAILY

    def test_frozen(self) -> None:
        kline = RawKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("102"),
            low=Decimal("99"), close=Decimal("101"), volume=1000,
        )
        with pytest.raises(FrozenInstanceError):
            kline.high = Decimal("200")  # type: ignore[misc]


class TestStandardKLine:
    def test_create_with_defaults(self) -> None:
        kline = StandardKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("102"),
            low=Decimal("99"), close=Decimal("101"), volume=1000,
        )
        assert kline.original_count == 1
        assert kline.direction == Direction.UP

    def test_frozen(self) -> None:
        kline = StandardKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("102"),
            low=Decimal("99"), close=Decimal("101"), volume=1000,
        )
        with pytest.raises(FrozenInstanceError):
            kline.low = Decimal("50")  # type: ignore[misc]


class TestFractal:
    def test_create(self) -> None:
        k1 = StandardKLine(datetime(2024, 1, 2), Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000)
        k2 = StandardKLine(datetime(2024, 1, 3), Decimal("101"), Decimal("105"), Decimal("100"), Decimal("104"), 1100)
        k3 = StandardKLine(datetime(2024, 1, 4), Decimal("104"), Decimal("103"), Decimal("98"), Decimal("99"), 1200)
        fractal = Fractal(
            type=FractalType.TOP,
            timestamp=datetime(2024, 1, 3),
            extreme_value=Decimal("105"),
            kline_index=1,
            elements=(k1, k2, k3),
        )
        assert fractal.type == FractalType.TOP
        assert fractal.extreme_value == Decimal("105")


class TestStroke:
    def test_price_range(self) -> None:
        k1 = StandardKLine(datetime(2024, 1, 2), Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000)
        k2 = StandardKLine(datetime(2024, 1, 3), Decimal("101"), Decimal("105"), Decimal("100"), Decimal("104"), 1100)
        k3 = StandardKLine(datetime(2024, 1, 4), Decimal("104"), Decimal("103"), Decimal("98"), Decimal("99"), 1200)
        f1 = Fractal(FractalType.BOTTOM, datetime(2024, 1, 2), Decimal("99"), 0, (k1, k2, k3))
        f2 = Fractal(FractalType.TOP, datetime(2024, 1, 3), Decimal("105"), 1, (k1, k2, k3))

        stroke = Stroke(
            direction=Direction.UP,
            start_fractal=f1,
            end_fractal=f2,
            high=Decimal("105"),
            low=Decimal("99"),
            kline_count=5,
            start_time=datetime(2024, 1, 2),
            end_time=datetime(2024, 1, 3),
        )
        assert stroke.price_range == Decimal("6")


class TestSegment:
    def test_stroke_count(self) -> None:
        k1 = StandardKLine(datetime(2024, 1, 2), Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000)
        k2 = StandardKLine(datetime(2024, 1, 3), Decimal("101"), Decimal("105"), Decimal("100"), Decimal("104"), 1100)
        k3 = StandardKLine(datetime(2024, 1, 4), Decimal("104"), Decimal("103"), Decimal("98"), Decimal("99"), 1200)
        f1 = Fractal(FractalType.BOTTOM, datetime(2024, 1, 2), Decimal("99"), 0, (k1, k2, k3))
        f2 = Fractal(FractalType.TOP, datetime(2024, 1, 3), Decimal("105"), 1, (k1, k2, k3))

        s1 = Stroke(Direction.UP, f1, f2, Decimal("105"), Decimal("99"), 5)
        s2 = Stroke(Direction.DOWN, f2, f1, Decimal("105"), Decimal("99"), 5)
        s3 = Stroke(Direction.UP, f1, f2, Decimal("105"), Decimal("99"), 5)

        segment = Segment(
            direction=Direction.UP,
            strokes=(s1, s2, s3),
            high=Decimal("105"),
            low=Decimal("99"),
        )
        assert segment.stroke_count == 3


class TestMACDValue:
    def test_defaults(self) -> None:
        v = MACDValue()
        assert v.dif == Decimal("0")
        assert v.dea == Decimal("0")
        assert v.histogram == Decimal("0")


class TestPipelineState:
    def test_empty_state(self) -> None:
        state = PipelineState()
        assert len(state.standard_klines) == 0
        assert state.trend is None
        assert len(state.signals) == 0


class TestSignal:
    def test_create(self) -> None:
        sig = Signal(
            signal_type=SignalType.B1,
            level=TimeFrame.DAILY,
            instrument="AAPL",
            timestamp=datetime(2024, 1, 15),
            price=Decimal("150.25"),
            strength=Decimal("0.85"),
            source_lesson="第024课",
        )
        assert sig.signal_type == SignalType.B1
        assert sig.small_to_large is False
