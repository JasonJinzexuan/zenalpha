"""Walk-forward validation and Monte Carlo simulation.

Validates backtest robustness by testing on unseen data windows
and randomizing trade sequences.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from decimal import Decimal

from chanquant.core.objects import BacktestMetrics, RawKLine, Trade

from chanquant.backtest.engine import BacktestEngine
from chanquant.backtest.metrics import calculate_metrics

_ZERO = Decimal("0")


class WalkForwardValidator:
    """Split data into train/test windows and validate on each test period."""

    def __init__(
        self,
        market_cap_tier: str = "mid_cap",
    ) -> None:
        self._market_cap_tier = market_cap_tier

    def validate(
        self,
        klines: dict[str, Sequence[RawKLine]],
        train_ratio: float = 0.7,
        n_splits: int = 5,
        initial_cash: Decimal = Decimal("1000000"),
    ) -> list[BacktestMetrics]:
        """Run walk-forward validation across n_splits windows.

        Each window: train on first train_ratio%, test on the rest.
        Returns metrics for each test window.
        """
        # Use the first instrument to determine total length
        first_key = next(iter(klines))
        total_bars = len(klines[first_key])
        window_size = total_bars // n_splits

        results: list[BacktestMetrics] = []
        for i in range(n_splits):
            start = i * window_size
            end = start + window_size if i < n_splits - 1 else total_bars
            split_point = start + int((end - start) * train_ratio)

            # Extract test window for each instrument
            test_klines = {
                inst: bars[split_point:end] for inst, bars in klines.items()
            }

            engine = BacktestEngine(market_cap_tier=self._market_cap_tier)
            metrics, _ = engine.run(test_klines, initial_cash)
            results.append(metrics)

        return results


class MonteCarloTest:
    """Randomize trade sequences to estimate statistical significance."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def test(
        self,
        trades: Sequence[Trade],
        n_simulations: int = 1000,
        initial_equity: Decimal = Decimal("1000000"),
    ) -> dict[str, Decimal]:
        """Shuffle trade PnLs and compute equity curve distribution.

        Returns:
            p_value: fraction of shuffled curves with higher final equity
            median_equity: median final equity across simulations
            ci_lower_5: 5th percentile final equity
            ci_upper_95: 95th percentile final equity
        """
        if not trades:
            return {
                "p_value": Decimal("1"),
                "median_equity": initial_equity,
                "ci_lower_5": initial_equity,
                "ci_upper_95": initial_equity,
            }

        pnls = [t.pnl for t in trades]
        actual_final = _equity_from_pnls(pnls, initial_equity)

        finals: list[Decimal] = []
        for _ in range(n_simulations):
            shuffled = list(pnls)
            self._rng.shuffle(shuffled)
            finals.append(_equity_from_pnls(shuffled, initial_equity))

        finals.sort()
        better_count = sum(1 for f in finals if f >= actual_final)
        p_value = Decimal(better_count) / Decimal(n_simulations)

        return {
            "p_value": p_value,
            "median_equity": _percentile(finals, 50),
            "ci_lower_5": _percentile(finals, 5),
            "ci_upper_95": _percentile(finals, 95),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _equity_from_pnls(
    pnls: list[Decimal], initial: Decimal
) -> Decimal:
    equity = initial
    for pnl in pnls:
        equity += pnl
    return equity


def _percentile(sorted_values: list[Decimal], pct: int) -> Decimal:
    """Simple percentile from a sorted list."""
    if not sorted_values:
        return _ZERO
    idx = int(len(sorted_values) * pct / 100)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]
