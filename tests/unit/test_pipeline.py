"""Tests for the full analysis pipeline."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from chanquant.core.objects import RawKLine, TimeFrame


class TestAnalysisPipeline:
    def test_imports(self) -> None:
        from chanquant.core.pipeline import AnalysisPipeline
        pipeline = AnalysisPipeline(level=TimeFrame.DAILY, instrument="TEST")
        assert pipeline is not None

    def test_feed_single_kline(self) -> None:
        from chanquant.core.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(level=TimeFrame.DAILY, instrument="AAPL")
        kline = RawKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("102"),
            low=Decimal("99"), close=Decimal("101"),
            volume=1000000,
        )
        state = pipeline.feed(kline)
        assert state is not None
        assert len(state.macd_values) == 1

    def test_feed_multiple_klines(self, uptrend_klines) -> None:
        from chanquant.core.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(level=TimeFrame.DAILY, instrument="AAPL")
        state = None
        for kline in uptrend_klines:
            state = pipeline.feed(kline)

        assert state is not None
        assert len(state.standard_klines) > 0
        assert len(state.macd_values) == len(uptrend_klines)

    def test_pipeline_with_downtrend(self, downtrend_klines) -> None:
        from chanquant.core.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(level=TimeFrame.DAILY, instrument="TSLA")
        state = None
        for kline in downtrend_klines:
            state = pipeline.feed(kline)

        assert state is not None
        assert len(state.standard_klines) > 0

    def test_pipeline_with_consolidation(self, consolidation_klines) -> None:
        from chanquant.core.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(level=TimeFrame.DAILY, instrument="MSFT")
        state = None
        for kline in consolidation_klines:
            state = pipeline.feed(kline)

        assert state is not None
