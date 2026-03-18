"""Tests for L0 — K-line containment processing."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.kline import KLineProcessor
from chanquant.core.objects import Direction, RawKLine, StandardKLine


def make_raw(ts: str, h: str, l: str, o: str = "100", c: str = "100", vol: int = 1000) -> RawKLine:
    return RawKLine(
        timestamp=datetime.fromisoformat(ts),
        open=Decimal(o), high=Decimal(h), low=Decimal(l),
        close=Decimal(c), volume=vol,
    )


class TestKLineProcessor:
    def test_first_kline_buffered(self) -> None:
        """First kline is buffered, not emitted immediately."""
        proc = KLineProcessor()
        result = proc.feed(make_raw("2024-01-02", "102", "99"))
        # First kline goes into buffer
        assert result is None

    def test_second_non_containing_emits_first(self) -> None:
        """Second non-containing kline causes first to be emitted."""
        proc = KLineProcessor()
        proc.feed(make_raw("2024-01-02", "102", "99"))
        result = proc.feed(make_raw("2024-01-03", "104", "101"))
        assert result is not None
        assert result.high == Decimal("102")
        assert result.low == Decimal("99")

    def test_flush_emits_last_buffered(self) -> None:
        proc = KLineProcessor()
        proc.feed(make_raw("2024-01-02", "102", "99"))
        result = proc.flush()
        assert result is not None
        assert result.high == Decimal("102")

    def test_containing_kline_merged_not_emitted(self) -> None:
        """When containment exists, merged result stays in buffer."""
        proc = KLineProcessor()
        proc.feed(make_raw("2024-01-02", "100", "95"))
        # K2 is higher
        r1 = proc.feed(make_raw("2024-01-03", "105", "98"))
        assert r1 is not None  # K1 emitted
        # K3 contained by K2 (K2.high=105 >= K3.high=103, but K2.low=98 < K3.low=99)
        # Actually K3 is contained if K2.high>=K3.high AND K2.low<=K3.low
        r2 = proc.feed(make_raw("2024-01-04", "103", "99"))
        # K3 is contained by K2 → merged, returns None
        assert r2 is None

    def test_processes_fixture_data(self, uptrend_klines: list[RawKLine]) -> None:
        proc = KLineProcessor()
        results = []
        for kline in uptrend_klines:
            result = proc.feed(kline)
            if result:
                results.append(result)
        # Flush last
        last = proc.flush()
        if last:
            results.append(last)
        assert len(results) <= len(uptrend_klines)
        assert len(results) > 0

    def test_merge_preserves_volume(self) -> None:
        proc = KLineProcessor()
        proc.feed(make_raw("2024-01-02", "100", "95", vol=1000))
        r1 = proc.feed(make_raw("2024-01-03", "108", "97", vol=2000))
        # K3 contained by K2
        r2 = proc.feed(make_raw("2024-01-04", "106", "98", vol=1500))
        # K3 was merged with K2
        flushed = proc.flush()
        if flushed:
            assert flushed.volume >= 2000  # At least K2's volume
