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
from chanquant.execution.position import check_portfolio_drawdown
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
from chanquant.risk.manager import RiskManager
from chanquant.strategy.models import StrategyParams, RiskParams

from chanquant.backtest.metrics import calculate_metrics
from chanquant.backtest.portfolio import PortfolioManager
from chanquant.backtest.slippage import SlippageModel

_ZERO = Decimal("0")
_ONE = Decimal("1")
_DEFAULT_STOP_LOSS_PCT = Decimal("0.05")
_MAX_POSITION_PCT = Decimal("0.1")
_ATR_PERIOD = 14

_ALLOWED_SIGNALS_ALL = frozenset({"B1", "B2", "B3", "S1", "S2", "S3"})

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
        strategy_params: StrategyParams | None = None,
        risk_params: RiskParams | None = None,
    ) -> None:
        self._portfolio = PortfolioManager()
        self._slippage = SlippageModel()
        self._nester = IntervalNester()
        self._risk_manager = RiskManager()
        # ATR series per instrument, populated in run()
        self._atr_data: dict[str, dict[datetime, Decimal]] = {}

        # Strategy params → signal filtering (what to trade)
        if strategy_params is not None:
            self._strategy_params = strategy_params
            self._min_depth = strategy_params.min_nesting_depth
            self._require_alignment = strategy_params.require_alignment
            self._allowed_signals = frozenset(strategy_params.allowed_signals)
            self._min_strength = strategy_params.min_signal_strength
            self._min_confidence = strategy_params.min_confidence
        else:
            self._strategy_params = StrategyParams()
            self._min_depth = min_nesting_depth
            self._require_alignment = require_alignment
            self._allowed_signals = _ALLOWED_SIGNALS_ALL
            self._min_strength = _ZERO
            self._min_confidence = Decimal("0.4")

        # Risk params → capital protection (how much to trade)
        if risk_params is not None:
            self._risk_params = risk_params
            self._stop_loss_atr_mult = risk_params.stop_loss_atr_mult
            # Fallback stop loss: use stop_loss_atr_mult * avg_atr_pct (~1-2%)
            # as a rough percentage when ATR data is unavailable
            self._stop_loss_pct = Decimal(str(
                float(risk_params.stop_loss_atr_mult) * 0.015
            ))
            self._max_position_pct = risk_params.max_position_pct
            self._max_positions = risk_params.max_concurrent_positions
            self._trailing_stop_enabled = risk_params.trailing_stop_enabled
            self._trailing_stop_pct = risk_params.trailing_stop_pct
        else:
            self._risk_params = RiskParams()
            self._stop_loss_atr_mult = Decimal("2")
            self._stop_loss_pct = stop_loss_pct
            self._max_position_pct = max_position_pct
            self._max_positions = 10
            self._trailing_stop_enabled = True
            self._trailing_stop_pct = Decimal("0.03")
        # Track high water mark per position for trailing stop
        self._position_hwm: dict[str, Decimal] = {}

    def run(
        self,
        multi_klines: dict[str, dict[TimeFrame, Sequence[RawKLine]]],
        initial_cash: Decimal = Decimal("1000000"),
        exec_level: TimeFrame = TimeFrame.DAILY,
    ) -> tuple[BacktestMetrics, Sequence[PortfolioSnapshot], list[dict], dict[str, dict]]:
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
            return BacktestMetrics(), (), [], {}

        # Phase 1: Run all pipelines, collect signals with timestamps
        all_signals = self._run_all_pipelines(multi_klines)

        # Phase 2: Build execution timeline from exec_level klines
        exec_klines: dict[str, Sequence[RawKLine]] = {}
        for inst in instruments:
            if exec_level in multi_klines[inst]:
                exec_klines[inst] = multi_klines[inst][exec_level]
        timeline = _build_timeline(exec_klines)
        if not timeline:
            return BacktestMetrics(), (), [], {}

        # Phase 2.5: Compute ATR per instrument from exec-level klines
        self._atr_data = {}
        for inst, bars in exec_klines.items():
            self._atr_data[inst] = _compute_atr_series(bars)

        # Phase 3: Walk timeline, execute trades via nesting + risk gate
        snapshot = _initial_snapshot(timeline[0][0], initial_cash)
        snapshots: list[PortfolioSnapshot] = [snapshot]
        trade_log: list[dict] = []
        processed_signals: set[str] = set()

        for timestamp, bars in timeline:
            snapshot = replace(snapshot, timestamp=timestamp)

            # 1. Stop losses (hard stop + trailing stop)
            snapshot = self._check_stops(snapshot, bars)

            # 1.5 Portfolio-level drawdown circuit breaker
            if snapshot.positions:
                current_dd = (
                    (snapshot.peak_equity - snapshot.equity) / snapshot.peak_equity
                    if snapshot.peak_equity > _ZERO else _ZERO
                )
                dd_action = check_portfolio_drawdown(
                    current_dd, self._risk_params.max_drawdown_pct,
                )
                if dd_action in ("clear_all", "suspend"):
                    # Force-close ALL positions
                    for pos in list(snapshot.positions):
                        bar = bars.get(pos.instrument)
                        if bar is not None:
                            snapshot = self._portfolio.close_position(
                                snapshot, pos.instrument, bar.close, "drawdown_breaker",
                            )
                            self._position_hwm.pop(pos.instrument, None)
                            trade_log.append({
                                "action": "SELL",
                                "instrument": pos.instrument,
                                "timestamp": str(timestamp),
                                "price": str(bar.close),
                                "signal": f"DD:{current_dd:.1%}",
                                "nesting_depth": 0,
                                "aligned": True,
                            })
                elif dd_action == "half_all":
                    # Close half of positions (worst performers first)
                    positions_by_pnl = sorted(
                        snapshot.positions,
                        key=lambda p: (
                            bars.get(p.instrument, p).close - p.entry_price  # type: ignore
                            if p.instrument in bars else _ZERO
                        ),
                    )
                    to_close = len(positions_by_pnl) // 2
                    for pos in positions_by_pnl[:to_close]:
                        bar = bars.get(pos.instrument)
                        if bar is not None:
                            snapshot = self._portfolio.close_position(
                                snapshot, pos.instrument, bar.close, "drawdown_reduce",
                            )
                            self._position_hwm.pop(pos.instrument, None)
                            trade_log.append({
                                "action": "SELL",
                                "instrument": pos.instrument,
                                "timestamp": str(timestamp),
                                "price": str(bar.close),
                                "signal": f"DD减仓:{current_dd:.1%}",
                                "nesting_depth": 0,
                                "aligned": True,
                            })

            # 2. Sell signal exits — relaxed: depth >= 1, skip risk gate
            #    Mirrors DecisionAgent: sell signals bypass risk manager
            for inst in bars:
                if not any(p.instrument == inst for p in snapshot.positions):
                    continue
                sell_sig = self._find_sell_signal(
                    all_signals.get(inst, {}), timestamp, processed_signals, inst,
                )
                if sell_sig is None:
                    continue
                sig_key = f"{inst}:{sell_sig.signal_type.value}:{sell_sig.timestamp}"
                processed_signals.add(sig_key)
                bar = bars[inst]
                old_snap = snapshot
                snapshot = self._try_close(snapshot, sell_sig, bar)
                if snapshot is not old_snap:
                    self._position_hwm.pop(inst, None)
                    trade_log.append({
                        "action": "SELL",
                        "instrument": inst,
                        "timestamp": str(timestamp),
                        "price": str(sell_sig.price),
                        "signal": sell_sig.signal_type.value,
                        "nesting_depth": 1,
                        "aligned": True,
                    })

            # 3. Buy signal entries — strict: nesting + alignment + confidence + risk gate
            for inst in bars:
                nested = self._find_nested_signals(
                    all_signals.get(inst, {}), timestamp
                )
                if nested is None or nested.nesting_depth < self._min_depth:
                    continue

                nesting_depth = nested.nesting_depth
                aligned = nested.direction_aligned

                if self._require_alignment and not aligned:
                    continue

                confidence = min(
                    Decimal("1"),
                    Decimal(nesting_depth) * Decimal("0.3")
                    + (Decimal("0.2") if aligned else _ZERO),
                )
                if confidence < self._min_confidence:
                    continue

                action_signal = (
                    nested.precise_signal
                    or nested.medium_signal
                    or nested.large_signal
                )
                if action_signal is None:
                    continue
                if not _is_buy_signal(action_signal.signal_type):
                    continue
                if action_signal.signal_type.value not in self._allowed_signals:
                    continue
                if action_signal.strength < self._min_strength:
                    continue

                # RiskManager gate
                nesting_result = {
                    "nesting_depth": nesting_depth,
                    "direction_aligned": aligned,
                    "confidence": str(confidence),
                    "per_level": {},
                }
                current_drawdown = (
                    (snapshot.peak_equity - snapshot.equity) / snapshot.peak_equity
                    if snapshot.peak_equity > _ZERO else _ZERO
                )
                atr_val = _ZERO
                atr_series = self._atr_data.get(inst, {})
                for ts in sorted(atr_series.keys(), reverse=True):
                    if ts <= timestamp:
                        atr_val = atr_series[ts]
                        break

                risk_result = self._risk_manager.evaluate(
                    nesting_result=nesting_result,
                    params=self._risk_params,
                    equity=snapshot.equity,
                    current_positions=len(snapshot.positions),
                    current_drawdown=current_drawdown,
                    atr_value=atr_val,
                    current_price=bars[inst].close,
                )
                if not risk_result.approved:
                    continue

                sig_key = f"{inst}:{action_signal.signal_type.value}:{action_signal.timestamp}"
                if sig_key in processed_signals:
                    continue
                processed_signals.add(sig_key)

                bar = bars[inst]
                old_snap = snapshot
                snapshot = self._try_open(snapshot, action_signal, bar)
                if snapshot is not old_snap:
                    large_sig = nested.large_signal
                    medium_sig = nested.medium_signal
                    precise_sig = nested.precise_signal
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

            # Update equity
            prices = {inst: bar.close for inst, bar in bars.items()}
            snapshot = self._portfolio.update_equity(snapshot, prices)
            snapshots.append(snapshot)

        # Force-close all remaining positions at last bar price
        if timeline:
            last_bars = timeline[-1][1]
            for position in list(snapshot.positions):
                bar = last_bars.get(position.instrument)
                if bar is not None:
                    snapshot = self._portfolio.close_position(
                        snapshot, position.instrument, bar.close, "backtest_end"
                    )
                    trade_log.append({
                        "action": "SELL",
                        "instrument": position.instrument,
                        "timestamp": str(timeline[-1][0]),
                        "price": str(bar.close),
                        "signal": "END",
                        "nesting_depth": 0,
                        "aligned": True,
                    })

        all_trades = snapshots[-1].trades
        metrics = calculate_metrics(snapshots, all_trades)

        # Decision-dimension stats (mirrors DecisionAgent logic)
        # Group by: nesting depth + alignment status
        decision_stats: dict[str, dict] = {}
        # Index closed trades by instrument+timestamp for P&L matching
        closed_by_inst: dict[str, list] = {}
        for trade in all_trades:
            closed_by_inst.setdefault(trade.instrument, []).append(trade)

        for entry in trade_log:
            if entry["action"] != "BUY":
                continue  # only count entry decisions
            depth = entry.get("nesting_depth", 0)
            aligned = entry.get("aligned", False)
            category = f"{depth}层嵌套{'✓对齐' if aligned else '✗不齐'}"
            if category not in decision_stats:
                decision_stats[category] = {"trades": 0, "wins": 0, "total_pnl": _ZERO}
            decision_stats[category]["trades"] += 1

            # Find matching closed trade for this instrument
            inst = entry["instrument"]
            if inst in closed_by_inst and closed_by_inst[inst]:
                closed = closed_by_inst[inst].pop(0)
                if closed.pnl > _ZERO:
                    decision_stats[category]["wins"] += 1
                decision_stats[category]["total_pnl"] += closed.pnl

        return metrics, tuple(snapshots), trade_log, decision_stats

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

    def _find_sell_signal(
        self,
        signals_by_tf: dict[TimeFrame, list[Signal]],
        current_time: datetime,
        processed: set[str],
        instrument: str,
    ) -> Signal | None:
        """Find any active sell signal (single-TF is enough for exits).

        Mirrors DecisionAgent: sell signals bypass risk gate and strict
        nesting requirements. Only needs one TF to confirm an exit.
        """
        best: Signal | None = None
        for tf, sigs in signals_by_tf.items():
            lookback = _SIGNAL_LOOKBACK.get(tf, timedelta(days=10))
            window_start = current_time - lookback
            for s in sigs:
                if s.signal_type not in (SignalType.S1, SignalType.S2, SignalType.S3):
                    continue
                if not (window_start <= s.timestamp <= current_time):
                    continue
                sig_key = f"{instrument}:{s.signal_type.value}:{s.timestamp}"
                if sig_key in processed:
                    continue
                if best is None or s.timestamp > best.timestamp:
                    best = s
        return best

    # ── Trade execution ──────────────────────────────────────────────────────

    def _get_stop_distance(self, instrument: str, timestamp: datetime, price: Decimal) -> Decimal:
        """Get ATR-based stop distance. Falls back to fixed % if no ATR."""
        atr_series = self._atr_data.get(instrument, {})
        # Find nearest ATR at or before timestamp
        atr = _ZERO
        for ts in sorted(atr_series.keys(), reverse=True):
            if ts <= timestamp:
                atr = atr_series[ts]
                break
        if atr > _ZERO:
            return atr * self._stop_loss_atr_mult
        # Fallback: fixed 5%
        return price * self._stop_loss_pct

    def _check_stops(
        self,
        snapshot: PortfolioSnapshot,
        bars: dict[str, RawKLine],
    ) -> PortfolioSnapshot:
        for position in list(snapshot.positions):
            bar = bars.get(position.instrument)
            if bar is None:
                continue

            inst = position.instrument
            exit_dir = Direction.DOWN if position.direction == Direction.UP else Direction.UP

            # Update high water mark for trailing stop
            if inst not in self._position_hwm:
                self._position_hwm[inst] = position.entry_price
            if position.direction == Direction.UP:
                self._position_hwm[inst] = max(self._position_hwm[inst], bar.high)
            else:
                self._position_hwm[inst] = min(self._position_hwm[inst], bar.low)

            # 1. ATR-based hard stop loss
            stop_dist = self._get_stop_distance(inst, bar.timestamp, position.entry_price)
            if _stop_triggered_atr(position, bar, stop_dist):
                stop_price = self._slippage.apply(bar.close, exit_dir, bar.volume, "mid_cap")
                snapshot = self._portfolio.close_position(snapshot, inst, stop_price, "stop_loss")
                self._position_hwm.pop(inst, None)
                continue

            # 2. Trailing stop
            if self._trailing_stop_enabled and self._trailing_stop_pct > _ZERO:
                hwm = self._position_hwm[inst]
                if position.direction == Direction.UP:
                    trail_stop = hwm * (_ONE - self._trailing_stop_pct)
                    if bar.low <= trail_stop:
                        stop_price = self._slippage.apply(bar.close, exit_dir, bar.volume, "mid_cap")
                        snapshot = self._portfolio.close_position(snapshot, inst, stop_price, "trailing_stop")
                        self._position_hwm.pop(inst, None)
                        continue
                else:
                    trail_stop = hwm * (_ONE + self._trailing_stop_pct)
                    if bar.high >= trail_stop:
                        stop_price = self._slippage.apply(bar.close, exit_dir, bar.volume, "mid_cap")
                        snapshot = self._portfolio.close_position(snapshot, inst, stop_price, "trailing_stop")
                        self._position_hwm.pop(inst, None)
                        continue

        return snapshot

    def _try_open(
        self, snapshot: PortfolioSnapshot, signal: Signal, bar: RawKLine,
    ) -> PortfolioSnapshot:
        if any(p.instrument == signal.instrument for p in snapshot.positions):
            return snapshot
        if len(snapshot.positions) >= self._max_positions:
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
        return bar.low <= position.entry_price * (_ONE - stop_pct)
    return bar.high >= position.entry_price * (_ONE + stop_pct)


def _stop_triggered_atr(position: Position, bar: RawKLine, stop_distance: Decimal) -> bool:
    """ATR-based stop: triggers when price moves stop_distance away from entry."""
    if position.direction == Direction.UP:
        return bar.low <= position.entry_price - stop_distance
    return bar.high >= position.entry_price + stop_distance


def _is_buy_signal(signal_type: SignalType) -> bool:
    return signal_type in (SignalType.B1, SignalType.B2, SignalType.B3)


def _position_size(equity: Decimal, price: Decimal, max_pct: Decimal) -> Decimal:
    if price <= _ZERO:
        return _ZERO
    return Decimal(int(equity * max_pct / price))


def _compute_atr_series(
    klines: Sequence[RawKLine], period: int = _ATR_PERIOD,
) -> dict[datetime, Decimal]:
    """Compute rolling ATR for a kline series. Returns {timestamp: atr}."""
    if len(klines) < 2:
        return {}
    trs: list[tuple[datetime, Decimal]] = []
    prev_close = klines[0].close
    for bar in klines[1:]:
        tr = max(
            bar.high - bar.low,
            abs(bar.high - prev_close),
            abs(bar.low - prev_close),
        )
        trs.append((bar.timestamp, tr))
        prev_close = bar.close

    result: dict[datetime, Decimal] = {}
    if len(trs) < period:
        # Not enough data — use simple average of all TRs
        avg = sum(t for _, t in trs) / Decimal(len(trs)) if trs else _ZERO
        for ts, _ in trs:
            result[ts] = avg
        return result

    # Initial SMA
    atr = sum(t for _, t in trs[:period]) / Decimal(period)
    result[trs[period - 1][0]] = atr
    # EMA-style rolling
    for i in range(period, len(trs)):
        atr = (atr * Decimal(period - 1) + trs[i][1]) / Decimal(period)
        result[trs[i][0]] = atr
    return result
