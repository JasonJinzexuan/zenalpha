"""Event-driven backtest engine for 缠论 signals.

Processes bars sequentially: analyse → check stops → process signals →
apply slippage → update portfolio → record snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from chanquant.core.objects import (
    BacktestMetrics,
    Direction,
    PortfolioSnapshot,
    Position,
    RawKLine,
    Signal,
    SignalType,
)

from chanquant.backtest.metrics import calculate_metrics
from chanquant.backtest.portfolio import PortfolioManager
from chanquant.backtest.slippage import SlippageModel

_ZERO = Decimal("0")
_DEFAULT_STOP_LOSS_PCT = Decimal("0.05")  # 5%
_MAX_POSITION_PCT = Decimal("0.1")  # 10% of equity per position


class BacktestEngine:
    """Run an event-driven backtest over historical K-line data.

    Supports survivorship bias mitigation by accepting delisted instruments.
    """

    def __init__(
        self,
        market_cap_tier: str = "mid_cap",
        stop_loss_pct: Decimal = _DEFAULT_STOP_LOSS_PCT,
        max_position_pct: Decimal = _MAX_POSITION_PCT,
        delisted: dict[str, datetime] | None = None,
    ) -> None:
        self._portfolio = PortfolioManager()
        self._slippage = SlippageModel()
        self._market_cap_tier = market_cap_tier
        self._stop_loss_pct = stop_loss_pct
        self._max_position_pct = max_position_pct
        # Map of instrument → delisting date for survivorship bias handling
        self._delisted = delisted or {}

    def run(
        self,
        klines: dict[str, Sequence[RawKLine]],
        initial_cash: Decimal = Decimal("1000000"),
    ) -> tuple[BacktestMetrics, Sequence[PortfolioSnapshot]]:
        """Execute backtest across all instruments.

        Returns metrics and the full sequence of portfolio snapshots.
        """
        from chanquant.core.pipeline import AnalysisPipeline

        timeline = _build_timeline(klines)
        if not timeline:
            return BacktestMetrics(), ()

        snapshot = _initial_snapshot(timeline[0][0], initial_cash)
        snapshots: list[PortfolioSnapshot] = [snapshot]

        pipelines: dict[str, AnalysisPipeline] = {
            inst: AnalysisPipeline(instrument=inst) for inst in klines
        }
        prev_signal_counts: dict[str, int] = {inst: 0 for inst in klines}

        for timestamp, bars in timeline:
            snapshot = replace(snapshot, timestamp=timestamp)

            # 1. Run pipeline analysis & collect only NEW signals
            signals = self._analyse_bars(pipelines, bars, prev_signal_counts)

            # 2. Force-close positions in delisted instruments
            snapshot = self._check_delistings(snapshot, timestamp, bars)

            # 3. Check stop losses
            snapshot = self._check_stops(snapshot, bars)

            # 4. Process new signals (skip delisted instruments)
            active_signals = [
                s for s in signals
                if s.instrument not in self._delisted
                or timestamp < self._delisted[s.instrument]
            ]
            snapshot = self._process_signals(snapshot, active_signals, bars)

            # 5. Update equity with current prices
            prices = {inst: bar.close for inst, bar in bars.items()}
            snapshot = self._portfolio.update_equity(snapshot, prices)

            snapshots.append(snapshot)

        all_trades = snapshots[-1].trades
        metrics = calculate_metrics(snapshots, all_trades)
        return metrics, tuple(snapshots)

    # ── Internal steps ───────────────────────────────────────────────────────

    def _check_delistings(
        self,
        snapshot: PortfolioSnapshot,
        timestamp: datetime,
        bars: dict[str, RawKLine],
    ) -> PortfolioSnapshot:
        """Force-close positions in instruments that have been delisted.

        Uses the last available price (survivorship bias mitigation).
        """
        for position in snapshot.positions:
            delist_date = self._delisted.get(position.instrument)
            if delist_date is None or timestamp < delist_date:
                continue
            bar = bars.get(position.instrument)
            if bar is not None:
                exit_price = bar.close
            else:
                exit_price = position.entry_price * Decimal("0.01")  # near-zero
            snapshot = self._portfolio.close_position(
                snapshot, position.instrument, exit_price, "delisted"
            )
        return snapshot

    def _analyse_bars(
        self,
        pipelines: dict[str, object],
        bars: dict[str, RawKLine],
        prev_counts: dict[str, int],
    ) -> list[Signal]:
        """Feed bars into pipelines and collect only NEW signals."""
        signals: list[Signal] = []
        for instrument, bar in bars.items():
            pipeline = pipelines[instrument]
            state = pipeline.feed(bar)  # type: ignore[union-attr]
            prev = prev_counts.get(instrument, 0)
            if len(state.signals) > prev:
                signals.extend(state.signals[prev:])
            prev_counts[instrument] = len(state.signals)
        return signals

    def _check_stops(
        self,
        snapshot: PortfolioSnapshot,
        bars: dict[str, RawKLine],
    ) -> PortfolioSnapshot:
        """Close positions that hit their stop loss."""
        for position in snapshot.positions:
            bar = bars.get(position.instrument)
            if bar is None:
                continue
            if _stop_triggered(position, bar, self._stop_loss_pct):
                stop_price = self._slippage.apply(
                    bar.close,
                    _exit_direction(position.direction),
                    bar.volume,
                    self._market_cap_tier,
                )
                snapshot = self._portfolio.close_position(
                    snapshot, position.instrument, stop_price, "stop_loss"
                )
        return snapshot

    def _process_signals(
        self,
        snapshot: PortfolioSnapshot,
        signals: list[Signal],
        bars: dict[str, RawKLine],
    ) -> PortfolioSnapshot:
        """Open or close positions based on new signals."""
        for signal in signals:
            bar = bars.get(signal.instrument)
            if bar is None:
                continue

            if _is_buy_signal(signal.signal_type):
                snapshot = self._try_open(snapshot, signal, bar)
            else:
                snapshot = self._try_close(snapshot, signal, bar)
        return snapshot

    def _try_open(
        self,
        snapshot: PortfolioSnapshot,
        signal: Signal,
        bar: RawKLine,
    ) -> PortfolioSnapshot:
        """Attempt to open a position with position sizing."""
        # Skip if already holding this instrument
        if any(p.instrument == signal.instrument for p in snapshot.positions):
            return snapshot

        exec_price = self._slippage.apply(
            signal.price, Direction.UP, bar.volume, self._market_cap_tier
        )
        quantity = _position_size(
            snapshot.equity, exec_price, self._max_position_pct
        )
        if quantity <= _ZERO:
            return snapshot

        return self._portfolio.open_position(
            snapshot,
            signal.instrument,
            exec_price,
            quantity,
            Direction.UP,
            signal,
        )

    def _try_close(
        self,
        snapshot: PortfolioSnapshot,
        signal: Signal,
        bar: RawKLine,
    ) -> PortfolioSnapshot:
        """Attempt to close an existing position."""
        if not any(p.instrument == signal.instrument for p in snapshot.positions):
            return snapshot

        exec_price = self._slippage.apply(
            signal.price, Direction.DOWN, bar.volume, self._market_cap_tier
        )
        return self._portfolio.close_position(
            snapshot, signal.instrument, exec_price, f"signal_{signal.signal_type.value}"
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_timeline(
    klines: dict[str, Sequence[RawKLine]],
) -> list[tuple[datetime, dict[str, RawKLine]]]:
    """Merge multi-instrument klines into a time-sorted list of bars."""
    time_map: dict[datetime, dict[str, RawKLine]] = {}
    for instrument, bars in klines.items():
        for bar in bars:
            if bar.timestamp not in time_map:
                time_map[bar.timestamp] = {}
            time_map[bar.timestamp][instrument] = bar
    return sorted(time_map.items(), key=lambda x: x[0])


def _initial_snapshot(timestamp: datetime, cash: Decimal) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=timestamp,
        cash=cash,
        equity=cash,
        peak_equity=cash,
    )


def _stop_triggered(
    position: Position, bar: RawKLine, stop_pct: Decimal
) -> bool:
    """Check if the bar's low (or high for shorts) breaches the stop."""
    if position.direction == Direction.UP:
        stop_price = position.entry_price * (Decimal("1") - stop_pct)
        return bar.low <= stop_price
    stop_price = position.entry_price * (Decimal("1") + stop_pct)
    return bar.high >= stop_price


def _exit_direction(direction: Direction) -> Direction:
    return Direction.DOWN if direction == Direction.UP else Direction.UP


def _is_buy_signal(signal_type: SignalType) -> bool:
    return signal_type in (SignalType.B1, SignalType.B2, SignalType.B3)


def _position_size(
    equity: Decimal, price: Decimal, max_pct: Decimal
) -> Decimal:
    """Calculate position size as whole shares."""
    if price <= _ZERO:
        return _ZERO
    max_value = equity * max_pct
    shares = int(max_value / price)
    return Decimal(shares)
