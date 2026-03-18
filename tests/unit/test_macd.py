"""Tests for MACD calculation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from chanquant.core.macd import IncrementalMACD, macd_area
from chanquant.core.objects import MACDValue


class TestIncrementalMACD:
    def test_initial_values_zero(self) -> None:
        macd = IncrementalMACD()
        result = macd.feed(Decimal("100"))
        assert result.dif == Decimal("0")
        assert result.dea == Decimal("0")

    def test_increasing_prices_positive_dif(self) -> None:
        macd = IncrementalMACD()
        results: list[MACDValue] = []
        for i in range(30):
            price = Decimal(str(100 + i))
            results.append(macd.feed(price))
        assert results[-1].dif > Decimal("0")

    def test_decreasing_prices_negative_dif(self) -> None:
        macd = IncrementalMACD()
        results: list[MACDValue] = []
        for i in range(30):
            price = Decimal(str(100 - i))
            results.append(macd.feed(price))
        assert results[-1].dif < Decimal("0")

    def test_custom_params(self) -> None:
        macd = IncrementalMACD(fast_period=8, slow_period=17, signal_period=9)
        for i in range(20):
            macd.feed(Decimal(str(100 + i)))

    def test_histogram_is_dif_minus_dea_times_2(self) -> None:
        macd = IncrementalMACD()
        for i in range(30):
            result = macd.feed(Decimal(str(100 + i * 0.5)))
        # histogram = 2 * (dif - dea)
        expected = (result.dif - result.dea) * 2
        assert abs(result.histogram - expected) < Decimal("0.001")


class TestMACDArea:
    def test_area_of_positive_values(self) -> None:
        values = [
            MACDValue(dif=Decimal("1"), dea=Decimal("0.5"), histogram=Decimal("0.5")),
            MACDValue(dif=Decimal("2"), dea=Decimal("1"), histogram=Decimal("1")),
            MACDValue(dif=Decimal("1.5"), dea=Decimal("1"), histogram=Decimal("0.5")),
        ]
        area = macd_area(values, 0, 3)
        assert area == Decimal("2")

    def test_area_of_negative_values(self) -> None:
        values = [
            MACDValue(histogram=Decimal("-0.5")),
            MACDValue(histogram=Decimal("-1")),
        ]
        area = macd_area(values, 0, 2)
        assert area == Decimal("1.5")

    def test_empty_range(self) -> None:
        values: list[MACDValue] = []
        area = macd_area(values, 0, 0)
        assert area == Decimal("0")
