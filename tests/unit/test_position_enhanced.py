"""Tests for enhanced position sizing: sector exposure and correlation."""

from datetime import datetime
from decimal import Decimal

from chanquant.core.objects import Direction, Position
from chanquant.execution.position import (
    check_correlation,
    check_portfolio_drawdown,
    check_sector_exposure,
    is_highly_correlated,
)


def _position(instrument: str = "AAPL", sector: str = "Technology") -> Position:
    return Position(
        instrument=instrument,
        entry_price=Decimal("150"),
        entry_time=datetime(2026, 3, 18),
        quantity=Decimal("100"),
        direction=Direction.UP,
        sector=sector,
    )


class TestSectorExposure:
    def test_within_limit(self):
        positions = [_position("AAPL", "Technology")]
        result = check_sector_exposure(
            positions, "Technology", Decimal("10000"), Decimal("100000"),
        )
        assert result is None  # 15000+10000=25000/100000=25% < 30%

    def test_exceeds_limit(self):
        positions = [
            _position("AAPL", "Technology"),
            _position("MSFT", "Technology"),
        ]
        result = check_sector_exposure(
            positions, "Technology", Decimal("20000"), Decimal("100000"),
        )
        # existing: 2*150*100=30000, new: 20000, total: 50000/100000=50% > 30%
        assert result == "sector_exposure_exceeded"

    def test_different_sector_ok(self):
        positions = [_position("AAPL", "Technology")]
        result = check_sector_exposure(
            positions, "Healthcare", Decimal("20000"), Decimal("100000"),
        )
        assert result is None


class TestCorrelation:
    def test_perfectly_correlated(self):
        xs = [Decimal(str(i)) for i in range(20)]
        ys = [Decimal(str(i)) for i in range(20)]
        corr = check_correlation(xs, ys)
        assert corr > Decimal("0.99")

    def test_uncorrelated(self):
        xs = [Decimal(str(i % 2)) for i in range(20)]
        ys = [Decimal(str((i + 1) % 2)) for i in range(20)]
        corr = check_correlation(xs, ys)
        assert corr < Decimal("0")

    def test_short_series_returns_zero(self):
        xs = [Decimal("1"), Decimal("2")]
        ys = [Decimal("1"), Decimal("2")]
        assert check_correlation(xs, ys) == Decimal("0")

    def test_highly_correlated_check(self):
        xs = [Decimal(str(i * 2)) for i in range(20)]
        ys = [Decimal(str(i * 2 + 1)) for i in range(20)]
        assert is_highly_correlated(xs, ys)


class TestDrawdownThresholds:
    def test_below_10_no_action(self):
        assert check_portfolio_drawdown(Decimal("0.08")) is None

    def test_10_half_all(self):
        assert check_portfolio_drawdown(Decimal("0.12")) == "half_all"

    def test_15_clear_all(self):
        assert check_portfolio_drawdown(Decimal("0.16")) == "clear_all"

    def test_20_suspend(self):
        assert check_portfolio_drawdown(Decimal("0.22")) == "suspend"
