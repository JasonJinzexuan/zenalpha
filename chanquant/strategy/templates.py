"""Predefined strategy templates.

Five templates covering aggressive → conservative spectrum.
Users can clone and customize via the Strategy Lab.
"""

from __future__ import annotations

from decimal import Decimal

from chanquant.strategy.models import StrategyParams, RiskParams, StrategyTemplate

AGGRESSIVE = StrategyTemplate(
    name="aggressive",
    description="高频多信号，适合低波动趋势明确的市场",
    strategy=StrategyParams(
        min_nesting_depth=2,
        min_confidence=Decimal("0.3"),
        divergence_ratio_max=Decimal("0.9"),
        min_signal_strength=Decimal("0.2"),
        allowed_signals=["B1", "B2", "B3", "S1", "S2", "S3"],
        signal_expiry_bars=30,
    ),
    risk=RiskParams(
        stop_loss_atr_mult=Decimal("1.5"),
        take_profit_atr_mult=Decimal("3.0"),
        trailing_stop_enabled=True,
        max_position_pct=Decimal("0.08"),
        max_concurrent_positions=8,
        max_daily_loss_pct=Decimal("0.04"),
        max_weekly_loss_pct=Decimal("0.10"),
        max_drawdown_pct=Decimal("0.20"),
        regime_filter=["EXTREME"],
    ),
    min_win_rate=Decimal("0.42"),
    min_profit_factor=Decimal("1.3"),
    max_allowed_drawdown=Decimal("0.25"),
    min_sharpe=Decimal("0.6"),
)

MODERATE = StrategyTemplate(
    name="moderate",
    description="平衡型，过滤弱信号，适合大多数市场环境",
    strategy=StrategyParams(
        min_nesting_depth=2,
        min_confidence=Decimal("0.5"),
        divergence_ratio_max=Decimal("0.7"),
        min_signal_strength=Decimal("0.4"),
        allowed_signals=["B1", "B2", "S1", "S2"],
        signal_expiry_bars=20,
    ),
    risk=RiskParams(
        stop_loss_atr_mult=Decimal("2.0"),
        take_profit_atr_mult=Decimal("4.0"),
        trailing_stop_enabled=True,
        max_position_pct=Decimal("0.05"),
        max_concurrent_positions=5,
        max_daily_loss_pct=Decimal("0.03"),
        max_weekly_loss_pct=Decimal("0.08"),
        max_drawdown_pct=Decimal("0.15"),
        regime_filter=["EXTREME", "HIGH_VOL"],
    ),
    min_win_rate=Decimal("0.45"),
    min_profit_factor=Decimal("1.5"),
    max_allowed_drawdown=Decimal("0.20"),
    min_sharpe=Decimal("0.8"),
)

CONSERVATIVE = StrategyTemplate(
    name="conservative",
    description="高确定性，只做最强信号，严格风控",
    strategy=StrategyParams(
        min_nesting_depth=3,
        min_confidence=Decimal("0.6"),
        divergence_ratio_max=Decimal("0.5"),
        min_signal_strength=Decimal("0.5"),
        allowed_signals=["B1", "S1"],
        signal_expiry_bars=15,
    ),
    risk=RiskParams(
        stop_loss_atr_mult=Decimal("2.5"),
        take_profit_atr_mult=Decimal("5.0"),
        trailing_stop_enabled=True,
        max_position_pct=Decimal("0.03"),
        max_concurrent_positions=3,
        max_daily_loss_pct=Decimal("0.02"),
        max_weekly_loss_pct=Decimal("0.05"),
        max_drawdown_pct=Decimal("0.10"),
        regime_filter=["EXTREME", "HIGH_VOL"],
    ),
    min_win_rate=Decimal("0.50"),
    min_profit_factor=Decimal("1.8"),
    max_allowed_drawdown=Decimal("0.15"),
    min_sharpe=Decimal("1.0"),
)

SCALP = StrategyTemplate(
    name="scalp",
    description="短线快进快出，小仓位高频率",
    strategy=StrategyParams(
        min_nesting_depth=2,
        min_confidence=Decimal("0.4"),
        divergence_ratio_max=Decimal("0.8"),
        min_signal_strength=Decimal("0.3"),
        allowed_signals=["B1", "B2", "B3", "S1", "S2", "S3"],
        signal_expiry_bars=10,
        exit_on_reverse_signal=True,
    ),
    risk=RiskParams(
        stop_loss_atr_mult=Decimal("1.0"),
        take_profit_atr_mult=Decimal("2.0"),
        trailing_stop_enabled=True,
        max_position_pct=Decimal("0.02"),
        max_concurrent_positions=10,
        max_daily_loss_pct=Decimal("0.03"),
        max_weekly_loss_pct=Decimal("0.08"),
        max_drawdown_pct=Decimal("0.15"),
        regime_filter=["EXTREME"],
    ),
    min_win_rate=Decimal("0.48"),
    min_profit_factor=Decimal("1.4"),
    max_allowed_drawdown=Decimal("0.20"),
    min_sharpe=Decimal("0.7"),
)

SWING = StrategyTemplate(
    name="swing",
    description="中长线波段，大级别确认，持仓时间长",
    strategy=StrategyParams(
        min_nesting_depth=3,
        min_confidence=Decimal("0.5"),
        divergence_ratio_max=Decimal("0.6"),
        min_signal_strength=Decimal("0.4"),
        allowed_signals=["B1", "B2", "S1", "S2"],
        signal_expiry_bars=40,
    ),
    risk=RiskParams(
        stop_loss_atr_mult=Decimal("3.0"),
        take_profit_atr_mult=Decimal("6.0"),
        trailing_stop_enabled=True,
        max_position_pct=Decimal("0.06"),
        max_concurrent_positions=4,
        max_daily_loss_pct=Decimal("0.03"),
        max_weekly_loss_pct=Decimal("0.08"),
        max_drawdown_pct=Decimal("0.18"),
        regime_filter=["EXTREME", "HIGH_VOL"],
    ),
    min_win_rate=Decimal("0.45"),
    min_profit_factor=Decimal("1.6"),
    max_allowed_drawdown=Decimal("0.22"),
    min_sharpe=Decimal("0.8"),
)

_TEMPLATES: dict[str, StrategyTemplate] = {
    t.name: t for t in [AGGRESSIVE, MODERATE, CONSERVATIVE, SCALP, SWING]
}


def get_template(name: str) -> StrategyTemplate | None:
    return _TEMPLATES.get(name)


def list_templates() -> list[StrategyTemplate]:
    return list(_TEMPLATES.values())
