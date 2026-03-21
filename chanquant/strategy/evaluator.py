"""Strategy evaluator — run backtest and check qualification gates."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from chanquant.backtest.metrics import calculate_metrics
from chanquant.backtest.nesting_engine import NestingBacktestEngine
from chanquant.core.objects import (
    BacktestMetrics,
    PortfolioSnapshot,
    RawKLine,
    TimeFrame,
)
from chanquant.strategy.models import StrategyParams, RiskParams, StrategyTemplate

_ZERO = Decimal("0")

# Fields that belong to StrategyParams vs RiskParams
_STRATEGY_FIELDS = set(StrategyParams.model_fields.keys())
_RISK_FIELDS = set(RiskParams.model_fields.keys())


def evaluate_strategy(
    template: StrategyTemplate,
    multi_klines: dict[str, dict[TimeFrame, Sequence[RawKLine]]],
    initial_cash: Decimal = Decimal("1000000"),
) -> dict[str, Any]:
    """Run backtest with strategy + risk params, return metrics + qualification."""

    engine = NestingBacktestEngine(
        strategy_params=template.strategy,
        risk_params=template.risk,
    )
    metrics, snapshots, trade_log, signal_stats = engine.run(
        multi_klines, initial_cash,
    )

    qualified = _check_qualification(metrics, template)

    # Build equity curve (sampled for frontend)
    equity_curve = _sample_equity_curve(snapshots, max_points=200)

    return {
        "strategy": template.name,
        "qualified": qualified,
        "metrics": {
            "total_return": str(metrics.total_return),
            "annualized_return": str(metrics.annualized_return),
            "sharpe_ratio": str(metrics.sharpe_ratio),
            "sortino_ratio": str(metrics.sortino_ratio),
            "calmar_ratio": str(metrics.calmar_ratio),
            "max_drawdown": str(metrics.max_drawdown),
            "win_rate": str(metrics.win_rate),
            "profit_factor": str(metrics.profit_factor),
            "total_trades": metrics.total_trades,
            "avg_trade_pnl": str(metrics.avg_trade_pnl),
        },
        "qualification": {
            "win_rate": {
                "value": str(metrics.win_rate),
                "threshold": str(template.min_win_rate),
                "pass": metrics.win_rate >= template.min_win_rate,
            },
            "profit_factor": {
                "value": str(metrics.profit_factor),
                "threshold": str(template.min_profit_factor),
                "pass": metrics.profit_factor >= template.min_profit_factor,
            },
            "max_drawdown": {
                "value": str(metrics.max_drawdown),
                "threshold": str(template.max_allowed_drawdown),
                "pass": metrics.max_drawdown <= template.max_allowed_drawdown,
            },
            "sharpe_ratio": {
                "value": str(metrics.sharpe_ratio),
                "threshold": str(template.min_sharpe),
                "pass": metrics.sharpe_ratio >= template.min_sharpe,
            },
        },
        "signal_stats": _format_signal_stats(signal_stats),
        "trade_count": len(trade_log),
        "trade_log": trade_log,
        "equity_curve": equity_curve,
        "strategy_params": template.strategy.model_dump(mode="json"),
        "risk_params": template.risk.model_dump(mode="json"),
    }


def evaluate_sensitivity(
    base_strategy: StrategyParams,
    base_risk: RiskParams,
    param_name: str,
    values: list[Decimal],
    multi_klines: dict[str, dict[TimeFrame, Sequence[RawKLine]]],
    initial_cash: Decimal = Decimal("1000000"),
) -> list[dict[str, Any]]:
    """Run backtest across multiple values of a single parameter."""

    results = []
    for val in values:
        # Determine which model the param belongs to and update accordingly
        if param_name in _STRATEGY_FIELDS:
            s_dict = base_strategy.model_dump()
            s_dict[param_name] = val
            strategy = StrategyParams(**s_dict)
            risk = base_risk
        elif param_name in _RISK_FIELDS:
            strategy = base_strategy
            r_dict = base_risk.model_dump()
            r_dict[param_name] = val
            risk = RiskParams(**r_dict)
        else:
            continue

        engine = NestingBacktestEngine(strategy_params=strategy, risk_params=risk)
        metrics, _, trade_log, _ = engine.run(multi_klines, initial_cash)

        results.append({
            "param_value": str(val),
            "win_rate": str(metrics.win_rate),
            "profit_factor": str(metrics.profit_factor),
            "max_drawdown": str(metrics.max_drawdown),
            "sharpe_ratio": str(metrics.sharpe_ratio),
            "total_trades": metrics.total_trades,
            "total_return": str(metrics.total_return),
        })

    return results


def _check_qualification(metrics: BacktestMetrics, template: StrategyTemplate) -> bool:
    if metrics.total_trades < 10:
        return False
    return (
        metrics.win_rate >= template.min_win_rate
        and metrics.profit_factor >= template.min_profit_factor
        and metrics.max_drawdown <= template.max_allowed_drawdown
        and metrics.sharpe_ratio >= template.min_sharpe
    )


def _sample_equity_curve(
    snapshots: Sequence[PortfolioSnapshot], max_points: int = 200,
) -> list[dict[str, str]]:
    if len(snapshots) <= max_points:
        step = 1
    else:
        step = len(snapshots) // max_points

    return [
        {"timestamp": str(s.timestamp), "equity": str(s.equity)}
        for i, s in enumerate(snapshots)
        if i % step == 0 or i == len(snapshots) - 1
    ]


def _format_signal_stats(stats: dict[str, dict]) -> list[dict[str, Any]]:
    result = []
    for sig_type, data in sorted(stats.items()):
        trades = data["trades"]
        wins = data["wins"]
        win_rate = Decimal(wins) / Decimal(trades) if trades > 0 else _ZERO
        result.append({
            "signal_type": sig_type,
            "trades": trades,
            "wins": wins,
            "win_rate": str(win_rate),
            "total_pnl": str(data["total_pnl"]),
        })
    return result
