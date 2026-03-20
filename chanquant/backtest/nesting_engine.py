"""Multi-timeframe backtest engine with interval nesting (区间套回测引擎).

Runs 4 pipelines per instrument (1w/1d/30m/5m), merges signals via
IntervalNester, and only executes trades on aligned multi-timeframe signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from chanquant.core.nesting import IntervalNester
from chanquant.core.objects import (
    BacktestMetrics,
    Direction,
    PortfolioSnapshot,
    Position,
    RawKLine,
    Signal,
    SignalType,
    TimeFrame,
)
from chanquant.core.pipeline import AnalysisPipeline

from chanquant.backtest.metrics import calculate_metrics
from chanquant.backtest.portfolio import PortfolioManager
from chanquant.backtest.slippage import SlippageModel

_ZERO = Decimal("0")
_DEFAULT_STOP_LOSS_PCT = Decimal("0.05")
_MAX_POSITION_PCT = Decimal("0.1")

# Timeframes used for nesting analysis (large → small)
_NESTING_LEVELS = [TimeFrame.WEEKLY, TimeFrame.DAILY, TimeFrame.MIN_30, TimeFrame.MIN_5]

# How long a signal stays "active" for nesting alignment
_SIGNAL_LOOKBACK: dict[TimeFrame, timedelta] = {
    TimeFrame.WEEKLY: timedelta(days=30),
    TimeFrame.DAILY: timedelta(days=10),
    TimeFrame.MIN_30: timedelta(days=3),
    TimeFrame.MIN_5: timedelta(days=1),
    TimeFrame.HOUR_1: timedelta(days=5),
}


class NestingBacktestEngine:
    """Multi-timeframe backtest with interval nesting confirmation."""

    def __init__(
        self,
        min_nesting_depth: int = 2,
        require_alignment: bool = True,
        stop_loss_pct: Decimal = _DEFAULT_STOP_LOSS_PCT,
        max_position_pct: Decimal = _MAX_POSITION_PCT,
    ) -> None:
        self._portfolio = PortfolioManager()
        self._slippage = SlippageModel()
        self._min_depth = min_nesting_depth
        self._require_alignment = require_alignment
        self._stop_loss_pct = stop_loss_pct
        self._max_position_pct = max_position_pct
        self._nester = IntervalNester()

    def run(
        self,
        multi_klines: dict[str, dict[TimeFrame, Sequence[RawKLine]]],
        initial_cash: Decimal = Decimal("1000000"),
        exec_level: TimeFrame = TimeFrame.DAILY,
    ) -> tuple[BacktestMetrics, Sequence[PortfolioSnapshot], list[dict]]:
        """Execute multi-timeframe backtest.

        Args:
            multi_klines: {instrument: {timeframe: klines}}
            initial_cash: starting cash
            exec_level: timeframe used for execution timeline

        Returns:
            (metrics, snapshots, trade_log)
        """
        instruments = list(multi_klines.keys())
        if not instruments:
            return BacktestMetrics(), (), []

        # Phase 1: Run all pipelines, collect signals with timestamps
        all_signals = self._run_all_pipelines(multi_klines)

        # Phase 2: Build execution timeline from exec_level klines
        exec_klines: dict[str, Sequence[RawKLine]] = {}
        for inst in instruments:
            if exec_level in multi_klines[inst]:
                exec_klines[inst] = multi_klines[inst][exec_level]
        timeline = _build_timeline(exec_klines)
        if not timeline:
            return BacktestMetrics(), (), []

        # Phase 3: Walk timeline, execute trades
        # Strategy: try nesting first; fall back to exec_level signals
        snapshot = _initial_snapshot(timeline[0][0], initial_cash)
        snapshots: list[PortfolioSnapshot] = [snapshot]
        trade_log: list[dict] = []
        processed_signals: set[str] = set()

        for timestamp, bars in timeline:
            snapshot = replace(snapshot, timestamp=timestamp)

            # Check stop losses
            snapshot = self._check_stops(snapshot, bars)

            for inst in bars:
                action_signal = None
                nesting_depth = 0
                aligned = False
                large_sig = None
                medium_sig = None
                precise_sig = None

                # Try nesting first
                nested = self._find_nested_signals(
                    all_signals.get(inst, {}), timestamp
                )
                if nested is not None and nested.nesting_depth >= self._min_depth:
                    if not self._require_alignment or nested.direction_aligned:
                        action_signal = (
                            nested.precise_signal
                            or nested.medium_signal
                            or nested.large_signal
                        )
                        nesting_depth = nested.nesting_depth
                        aligned = nested.direction_aligned
                        large_sig = nested.large_signal
                        medium_sig = nested.medium_signal
                        precise_sig = nested.precise_signal

                # Fallback: use exec_level signals directly
                if action_signal is None:
                    action_signal = self._find_exec_level_signal(
                        all_signals.get(inst, {}), exec_level, timestamp
                    )
                    if action_signal is not None:
                        nesting_depth = 1
                        aligned = True

                if action_signal is None:
                    continue

                # Dedup: don't process same signal twice
                sig_key = f"{inst}:{action_signal.signal_type.value}:{action_signal.timestamp}"
                if sig_key in processed_signals:
                    continue
                processed_signals.add(sig_key)

                bar = bars[inst]
                if _is_buy_signal(action_signal.signal_type):
                    old_snap = snapshot
                    snapshot = self._try_open(snapshot, action_signal, bar)
                    if snapshot is not old_snap:
                        trade_log.append({
                            "action": "BUY",
                            "instrument": inst,
                            "timestamp": str(timestamp),
                            "price": str(action_signal.price),
                            "signal": action_signal.signal_type.value,
                            "nesting_depth": nesting_depth,
                            "aligned": aligned,
                            "large": large_sig.signal_type.value if large_sig else None,
                            "medium": medium_sig.signal_type.value if medium_sig else None,
                            "precise": precise_sig.signal_type.value if precise_sig else None,
                        })
                else:
                    old_snap = snapshot
                    snapshot = self._try_close(snapshot, action_signal, bar)
                    if snapshot is not old_snap:
                        trade_log.append({
                            "action": "SELL",
                            "instrument": inst,
                            "timestamp": str(timestamp),
                            "price": str(action_signal.price),
                            "signal": action_signal.signal_type.value,
                            "nesting_depth": nesting_depth,
                            "aligned": aligned,
                        })

            # Update equity
            prices = {inst: bar.close for inst, bar in bars.items()}
            snapshot = self._portfolio.update_equity(snapshot, prices)
            snapshots.append(snapshot)

        metrics = calculate_metrics(snapshots, snapshots[-1].trades)
        return metrics, tuple(snapshots), trade_log

    # ── Phase 1: Pipeline execution ──────────────────────────────────────────

    def _run_all_pipelines(
        self,
        multi_klines: dict[str, dict[TimeFrame, Sequence[RawKLine]]],
    ) -> dict[str, dict[TimeFrame, list[Signal]]]:
        """Run pipeline per instrument per timeframe, collect all signals."""
        result: dict[str, dict[TimeFrame, list[Signal]]] = {}

        for inst, tf_klines in multi_klines.items():
            result[inst] = {}
            for tf, klines in tf_klines.items():
                pipeline = AnalysisPipeline(level=tf, instrument=inst)
                state = None
                for bar in klines:
                    state = pipeline.feed(bar)
                if state is not None:
                    result[inst][tf] = list(state.signals)

        return result

    # ── Phase 3: Nesting check ───────────────────────────────────────────────

    def _find_nested_signals(
        self,
        signals_by_tf: dict[TimeFrame, list[Signal]],
        current_time: datetime,
    ):
        """Find active signals at current_time and run nesting."""
        active: dict[TimeFrame, list[Signal]] = {}
        for tf, sigs in signals_by_tf.items():
            lookback = _SIGNAL_LOOKBACK.get(tf, timedelta(days=10))
            window_start = current_time - lookback
            active_sigs = [
                s for s in sigs
                if window_start <= s.timestamp <= current_time
            ]
            if active_sigs:
                active[tf] = active_sigs

        if not active:
            return None

        return self._nester.nest(active)

    def _find_exec_level_signal(
        self,
        signals_by_tf: dict[TimeFrame, list[Signal]],
        exec_level: TimeFrame,
        current_time: datetime,
    ) -> Signal | None:
        """Find the most recent exec-level signal active at current_time."""
        sigs = signals_by_tf.get(exec_level, [])
        if not sigs:
            return None
        lookback = _SIGNAL_LOOKBACK.get(exec_level, timedelta(days=10))
        window_start = current_time - lookback
        active = [
            s for s in sigs
            if window_start <= s.timestamp <= current_time
        ]
        if not active:
            return None
        # Return the most recent signal
        return max(active, key=lambda s: s.timestamp)

    # ── Trade execution ──────────────────────────────────────────────────────

    def _check_stops(
        self,
        snapshot: PortfolioSnapshot,
        bars: dict[str, RawKLine],
    ) -> PortfolioSnapshot:
        for position in snapshot.positions:
            bar = bars.get(position.instrument)
            if bar is None:
                continue
            if _stop_triggered(position, bar, self._stop_loss_pct):
                stop_price = self._slippage.apply(
                    bar.close,
                    Direction.DOWN if position.direction == Direction.UP else Direction.UP,
                    bar.volume,
                    "mid_cap",
                )
                snapshot = self._portfolio.close_position(
                    snapshot, position.instrument, stop_price, "stop_loss"
                )
        return snapshot

    def _try_open(
        self, snapshot: PortfolioSnapshot, signal: Signal, bar: RawKLine,
    ) -> PortfolioSnapshot:
        if any(p.instrument == signal.instrument for p in snapshot.positions):
            return snapshot
        exec_price = self._slippage.apply(
            signal.price, Direction.UP, bar.volume, "mid_cap"
        )
        quantity = _position_size(snapshot.equity, exec_price, self._max_position_pct)
        if quantity <= _ZERO:
            return snapshot
        return self._portfolio.open_position(
            snapshot, signal.instrument, exec_price, quantity,
            Direction.UP, signal,
        )

    def _try_close(
        self, snapshot: PortfolioSnapshot, signal: Signal, bar: RawKLine,
    ) -> PortfolioSnapshot:
        if not any(p.instrument == signal.instrument for p in snapshot.positions):
            return snapshot
        exec_price = self._slippage.apply(
            signal.price, Direction.DOWN, bar.volume, "mid_cap"
        )
        return self._portfolio.close_position(
            snapshot, signal.instrument, exec_price,
            f"signal_{signal.signal_type.value}",
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_timeline(
    klines: dict[str, Sequence[RawKLine]],
) -> list[tuple[datetime, dict[str, RawKLine]]]:
    time_map: dict[datetime, dict[str, RawKLine]] = {}
    for instrument, bars in klines.items():
        for bar in bars:
            if bar.timestamp not in time_map:
                time_map[bar.timestamp] = {}
            time_map[bar.timestamp][instrument] = bar
    return sorted(time_map.items(), key=lambda x: x[0])


def _initial_snapshot(timestamp: datetime, cash: Decimal) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=timestamp, cash=cash, equity=cash, peak_equity=cash,
    )


def _stop_triggered(position: Position, bar: RawKLine, stop_pct: Decimal) -> bool:
    if position.direction == Direction.UP:
        return bar.low <= position.entry_price * (Decimal("1") - stop_pct)
    return bar.high >= position.entry_price * (Decimal("1") + stop_pct)


def _is_buy_signal(signal_type: SignalType) -> bool:
    return signal_type in (SignalType.B1, SignalType.B2, SignalType.B3)


def _position_size(equity: Decimal, price: Decimal, max_pct: Decimal) -> Decimal:
    if price <= _ZERO:
        return _ZERO
    return Decimal(int(equity * max_pct / price))
