"""Performance metrics calculator for backtest results.

All calculations use Decimal. No pandas/numpy.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from chanquant.core.objects import BacktestMetrics, PortfolioSnapshot, Trade

_ZERO = Decimal("0")
_TRADING_DAYS_PER_YEAR = Decimal("252")


def calculate_metrics(
    snapshots: Sequence[PortfolioSnapshot],
    trades: Sequence[Trade],
    risk_free_rate: Decimal = Decimal("0.04"),
) -> BacktestMetrics:
    """Compute comprehensive backtest performance metrics."""
    if len(snapshots) < 2:
        return BacktestMetrics(total_trades=len(trades))

    total_return = _total_return(snapshots)
    n_days = Decimal(len(snapshots) - 1)
    ann_return = _annualized_return(total_return, n_days)

    daily_returns = _daily_returns(snapshots)
    ann_std = _annualized_std(daily_returns)
    sharpe = _sharpe_ratio(ann_return, risk_free_rate, ann_std)
    sortino = _sortino_ratio(ann_return, risk_free_rate, daily_returns)

    max_dd = _max_drawdown(snapshots)
    calmar = _calmar_ratio(ann_return, max_dd)
    max_dd_dur = _max_drawdown_duration(snapshots)

    win_rate = _win_rate(trades)
    profit_factor = _profit_factor(trades)
    avg_pnl = _avg_trade_pnl(trades)
    avg_hold = _avg_holding_period(trades)

    return BacktestMetrics(
        total_return=total_return,
        annualized_return=ann_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_dur,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=len(trades),
        avg_trade_pnl=avg_pnl,
        avg_holding_period=avg_hold,
    )


# ── Return calculations ─────────────────────────────────────────────────────


def _total_return(snapshots: Sequence[PortfolioSnapshot]) -> Decimal:
    first = snapshots[0].equity
    last = snapshots[-1].equity
    if first == _ZERO:
        return _ZERO
    return (last - first) / first


def _annualized_return(total_return: Decimal, n_days: Decimal) -> Decimal:
    if n_days == _ZERO:
        return _ZERO
    years = n_days / _TRADING_DAYS_PER_YEAR
    if years == _ZERO:
        return _ZERO
    # (1 + total_return)^(1/years) - 1
    base = Decimal("1") + total_return
    if base <= _ZERO:
        return Decimal("-1")
    exponent = Decimal("1") / years
    return _decimal_pow(base, exponent) - Decimal("1")


def _daily_returns(snapshots: Sequence[PortfolioSnapshot]) -> list[Decimal]:
    returns = []
    for i in range(1, len(snapshots)):
        prev_eq = snapshots[i - 1].equity
        if prev_eq == _ZERO:
            returns.append(_ZERO)
        else:
            returns.append((snapshots[i].equity - prev_eq) / prev_eq)
    return returns


# ── Risk metrics ─────────────────────────────────────────────────────────────


def _annualized_std(daily_returns: list[Decimal]) -> Decimal:
    if len(daily_returns) < 2:
        return _ZERO
    mean = sum(daily_returns) / Decimal(len(daily_returns))
    variance = sum((r - mean) ** 2 for r in daily_returns) / Decimal(
        len(daily_returns) - 1
    )
    daily_std = _decimal_sqrt(variance)
    return daily_std * _decimal_sqrt(_TRADING_DAYS_PER_YEAR)


def _sharpe_ratio(
    ann_return: Decimal, risk_free: Decimal, ann_std: Decimal
) -> Decimal:
    if ann_std == _ZERO:
        return _ZERO
    return (ann_return - risk_free) / ann_std


def _sortino_ratio(
    ann_return: Decimal,
    risk_free: Decimal,
    daily_returns: list[Decimal],
) -> Decimal:
    downside = [r for r in daily_returns if r < _ZERO]
    if len(downside) < 2:
        return _ZERO
    mean_down = sum(downside) / Decimal(len(downside))
    down_var = sum((r - mean_down) ** 2 for r in downside) / Decimal(
        len(downside) - 1
    )
    down_std = _decimal_sqrt(down_var) * _decimal_sqrt(_TRADING_DAYS_PER_YEAR)
    if down_std == _ZERO:
        return _ZERO
    return (ann_return - risk_free) / down_std


def _calmar_ratio(ann_return: Decimal, max_dd: Decimal) -> Decimal:
    if max_dd == _ZERO:
        return _ZERO
    return ann_return / max_dd


def _max_drawdown(snapshots: Sequence[PortfolioSnapshot]) -> Decimal:
    peak = _ZERO
    max_dd = _ZERO
    for s in snapshots:
        if s.equity > peak:
            peak = s.equity
        if peak > _ZERO:
            dd = (peak - s.equity) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _max_drawdown_duration(snapshots: Sequence[PortfolioSnapshot]) -> timedelta:
    peak = _ZERO
    peak_time = snapshots[0].timestamp
    max_dur = timedelta()
    for s in snapshots:
        if s.equity >= peak:
            peak = s.equity
            peak_time = s.timestamp
        else:
            dur = s.timestamp - peak_time
            if dur > max_dur:
                max_dur = dur
    return max_dur


# ── Trade statistics ─────────────────────────────────────────────────────────


def _win_rate(trades: Sequence[Trade]) -> Decimal:
    if not trades:
        return _ZERO
    wins = sum(1 for t in trades if t.pnl > _ZERO)
    return Decimal(wins) / Decimal(len(trades))


def _profit_factor(trades: Sequence[Trade]) -> Decimal:
    gross_profit = sum(t.pnl for t in trades if t.pnl > _ZERO)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < _ZERO))
    if gross_loss == _ZERO:
        return _ZERO
    return gross_profit / gross_loss


def _avg_trade_pnl(trades: Sequence[Trade]) -> Decimal:
    if not trades:
        return _ZERO
    return sum(t.pnl for t in trades) / Decimal(len(trades))


def _avg_holding_period(trades: Sequence[Trade]) -> timedelta:
    if not trades:
        return timedelta()
    total_seconds = sum(
        (t.exit_time - t.entry_time).total_seconds() for t in trades
    )
    return timedelta(seconds=total_seconds / len(trades))


# ── Math helpers ─────────────────────────────────────────────────────────────


def _decimal_sqrt(value: Decimal) -> Decimal:
    if value <= _ZERO:
        return _ZERO
    guess = value
    for _ in range(50):
        next_guess = (guess + value / guess) / Decimal("2")
        if abs(next_guess - guess) < Decimal("1E-20"):
            break
        guess = next_guess
    return guess


def _decimal_pow(base: Decimal, exponent: Decimal) -> Decimal:
    """Approximate base**exponent via exp(exponent * ln(base))."""
    if base <= _ZERO:
        return _ZERO
    ln_base = _decimal_ln(base)
    return _decimal_exp(exponent * ln_base)


def _decimal_ln(x: Decimal) -> Decimal:
    """Natural log via series expansion around 1."""
    if x <= _ZERO:
        return _ZERO
    # Reduce: x = m * 2^k so that 0.5 < m <= 1
    k = 0
    m = x
    while m > Decimal("2"):
        m /= Decimal("2")
        k += 1
    while m < Decimal("0.5"):
        m *= Decimal("2")
        k -= 1
    # ln(x) = k*ln(2) + ln(m), use series for ln(m) where m ~ 1
    ln2 = Decimal("0.6931471805599453094172321214581765680755")
    u = (m - Decimal("1")) / (m + Decimal("1"))
    u2 = u * u
    result = _ZERO
    term = u
    for n in range(1, 60, 2):
        result += term / Decimal(n)
        term *= u2
    return Decimal("2") * result + Decimal(k) * ln2


def _decimal_exp(x: Decimal) -> Decimal:
    """Exponential via Taylor series."""
    result = Decimal("1")
    term = Decimal("1")
    for i in range(1, 80):
        term *= x / Decimal(i)
        result += term
        if abs(term) < Decimal("1E-20"):
            break
    return result
