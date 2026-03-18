"""Tests for L1 — Fractal detection."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.fractal import FractalDetector
from chanquant.core.objects import Direction, FractalType, StandardKLine


def make_std(ts: str, h: str, l: str) -> StandardKLine:
    return StandardKLine(
        timestamp=datetime.fromisoformat(ts),
        open=Decimal("100"), high=Decimal(h), low=Decimal(l),
        close=Decimal("100"), volume=1000, direction=Direction.UP,
    )


class TestFractalDetector:
    def test_top_fractal(self) -> None:
        detector = FractalDetector()
        detector.feed(make_std("2024-01-02", "102", "99"))
        detector.feed(make_std("2024-01-03", "106", "101"))
        result = detector.feed(make_std("2024-01-04", "103", "98"))
        assert result is not None
        assert result.type == FractalType.TOP
        assert result.extreme_value == Decimal("106")

    def test_bottom_fractal(self) -> None:
        detector = FractalDetector()
        detector.feed(make_std("2024-01-02", "105", "100"))
        detector.feed(make_std("2024-01-03", "102", "96"))
        result = detector.feed(make_std("2024-01-04", "104", "99"))
        assert result is not None
        assert result.type == FractalType.BOTTOM
        assert result.extreme_value == Decimal("96")

    def test_no_fractal_monotonic(self) -> None:
        detector = FractalDetector()
        detector.feed(make_std("2024-01-02", "100", "95"))
        detector.feed(make_std("2024-01-03", "102", "97"))
        result = detector.feed(make_std("2024-01-04", "104", "99"))
        assert result is None

    def test_alternation_same_type_keeps_higher_top(self) -> None:
        detector = FractalDetector()
        # First top at 106
        detector.feed(make_std("2024-01-02", "102", "99"))
        detector.feed(make_std("2024-01-03", "106", "101"))
        f1 = detector.feed(make_std("2024-01-04", "103", "98"))
        assert f1 is not None
        assert f1.extreme_value == Decimal("106")

        # Second consecutive top at 108 — should replace (same type, higher)
        detector.feed(make_std("2024-01-05", "108", "103"))
        f2 = detector.feed(make_std("2024-01-08", "105", "100"))
        assert f2 is not None
        assert f2.extreme_value == Decimal("108")

    def test_processes_fixture_data(self, uptrend_klines) -> None:
        from chanquant.core.kline import KLineProcessor

        proc = KLineProcessor()
        detector = FractalDetector()
        fractal_count = 0
        for kline in uptrend_klines:
            std = proc.feed(kline)
            if std:
                result = detector.feed(std)
                if result:
                    fractal_count += 1
        # Also process flushed kline
        last = proc.flush()
        if last:
            result = detector.feed(last)
            if result:
                fractal_count += 1
        assert fractal_count > 0
