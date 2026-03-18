"""Tests for Market Regime Detection."""

from decimal import Decimal

from chanquant.core.objects import MarketRegime, TimeFrame
from chanquant.scoring.regime import RegimeDetector, RegimeInputs


class TestRegimeDetector:
    def test_low_vol_regime(self):
        detector = RegimeDetector()
        inputs = RegimeInputs(
            vix=Decimal("12"),
            credit_spread_bp=Decimal("150"),
            move_index=Decimal("70"),
            breadth_pct=Decimal("72"),
            sector_rotation_ratio=Decimal("2.0"),
        )
        assert detector.detect(inputs) == MarketRegime.LOW_VOL

    def test_normal_regime(self):
        detector = RegimeDetector()
        inputs = RegimeInputs(
            vix=Decimal("28"),
            credit_spread_bp=Decimal("350"),
            move_index=Decimal("120"),
            breadth_pct=Decimal("45"),
            sector_rotation_ratio=Decimal("0.9"),
        )
        assert detector.detect(inputs) == MarketRegime.NORMAL

    def test_high_vol_regime(self):
        detector = RegimeDetector()
        inputs = RegimeInputs(
            vix=Decimal("35"),
            credit_spread_bp=Decimal("450"),
            move_index=Decimal("130"),
            breadth_pct=Decimal("35"),
            sector_rotation_ratio=Decimal("0.8"),
        )
        assert detector.detect(inputs) == MarketRegime.HIGH_VOL

    def test_extreme_regime(self):
        detector = RegimeDetector()
        inputs = RegimeInputs(
            vix=Decimal("55"),
            credit_spread_bp=Decimal("600"),
            move_index=Decimal("180"),
            breadth_pct=Decimal("20"),
            sector_rotation_ratio=Decimal("0.5"),
        )
        assert detector.detect(inputs) == MarketRegime.EXTREME

    def test_adjust_timeframe_weight_extreme_blocks_intraday(self):
        detector = RegimeDetector()
        base = Decimal("2")
        adjusted = detector.adjust_timeframe_weight(
            MarketRegime.EXTREME, base, TimeFrame.MIN_5
        )
        assert adjusted == Decimal("0")

    def test_adjust_timeframe_weight_normal_unchanged(self):
        detector = RegimeDetector()
        base = Decimal("3")
        adjusted = detector.adjust_timeframe_weight(
            MarketRegime.NORMAL, base, TimeFrame.DAILY
        )
        assert adjusted == base
