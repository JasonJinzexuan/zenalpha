"""Strategy + Risk parameter models.

StrategyParams — signal filtering & entry logic (LLM decides)
RiskParams     — capital protection & position sizing (hard rules)
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class StrategyParams(BaseModel, frozen=True):
    """Signal filtering & entry/exit logic. LLM uses these as guidance."""

    # Entry filters
    min_nesting_depth: int = Field(2, ge=1, le=4)
    min_confidence: Decimal = Field(Decimal("0.4"), ge=0, le=1)
    require_alignment: bool = True
    divergence_ratio_max: Decimal = Field(
        Decimal("0.8"), ge=Decimal("0.1"), le=Decimal("1.0"),
        description="Max MACD area_c / area_a ratio for divergence validity",
    )
    min_signal_strength: Decimal = Field(Decimal("0.3"), ge=0, le=1)
    allowed_signals: list[str] = Field(
        default=["B1", "B2", "B3", "S1", "S2", "S3"],
    )
    signal_expiry_bars: int = Field(20, ge=5, le=100)

    # Exit logic
    exit_on_reverse_signal: bool = True


class RiskParams(BaseModel, frozen=True):
    """Capital protection & position sizing. Enforced as hard rules."""

    # Stop loss / take profit
    stop_loss_atr_mult: Decimal = Field(Decimal("2.0"), ge=Decimal("0.5"), le=Decimal("5.0"))
    take_profit_atr_mult: Decimal = Field(Decimal("4.0"), ge=Decimal("1.0"), le=Decimal("10.0"))
    trailing_stop_enabled: bool = True
    trailing_stop_pct: Decimal = Field(Decimal("0.03"), ge=Decimal("0"), le=Decimal("0.2"))

    # Position sizing
    max_position_pct: Decimal = Field(Decimal("0.05"), ge=Decimal("0.01"), le=Decimal("0.15"))
    use_atr_sizing: bool = True

    # Drawdown limits
    max_daily_loss_pct: Decimal = Field(Decimal("0.03"), ge=Decimal("0.01"), le=Decimal("0.10"))
    max_weekly_loss_pct: Decimal = Field(Decimal("0.08"), ge=Decimal("0.03"), le=Decimal("0.20"))
    max_drawdown_pct: Decimal = Field(Decimal("0.15"), ge=Decimal("0.05"), le=Decimal("0.30"))

    # Portfolio limits
    max_concurrent_positions: int = Field(5, ge=1, le=20)

    # Market regime filter
    regime_filter: list[str] = Field(
        default=["EXTREME"],
        description="Suppress signals when regime is in this list",
    )


class StrategyTemplate(BaseModel, frozen=True):
    """Named strategy with both strategy + risk params."""

    name: str
    description: str
    strategy: StrategyParams = StrategyParams()
    risk: RiskParams = RiskParams()

    # Backtest qualification gates
    min_win_rate: Decimal = Decimal("0.45")
    min_profit_factor: Decimal = Decimal("1.5")
    max_allowed_drawdown: Decimal = Decimal("0.20")
    min_sharpe: Decimal = Decimal("0.8")

    # Set after backtest
    qualified: bool = False


class BacktestRequest(BaseModel):
    """API request for running a strategy backtest."""

    strategy_name: str | None = None
    strategy: StrategyParams | None = None
    risk: RiskParams | None = None
    instruments: list[str] = Field(default=[])
    initial_cash: Decimal = Decimal("1000000")
    start_date: str | None = None
    end_date: str | None = None


class SensitivityRequest(BaseModel):
    """API request for parameter sensitivity analysis."""

    base_strategy: StrategyParams | None = None
    base_risk: RiskParams | None = None
    param_name: str
    values: list[str]
    instruments: list[str] = Field(default=[])
    initial_cash: Decimal = Decimal("1000000")
