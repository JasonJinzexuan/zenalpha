"""Immutable portfolio state manager.

All operations return NEW PortfolioSnapshot instances — never mutate.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from chanquant.core.objects import (
    Direction,
    Position,
    PortfolioSnapshot,
    Signal,
    Trade,
)


class PortfolioManager:
    """Stateless manager that produces new PortfolioSnapshot on every operation."""

    def open_position(
        self,
        snapshot: PortfolioSnapshot,
        instrument: str,
        price: Decimal,
        quantity: Decimal,
        direction: Direction,
        signal: Signal,
    ) -> PortfolioSnapshot:
        """Open a new position and deduct cash."""
        cost = price * quantity
        if cost > snapshot.cash:
            return snapshot  # insufficient funds

        position = Position(
            instrument=instrument,
            entry_price=price,
            entry_time=snapshot.timestamp,
            quantity=quantity,
            direction=direction,
            signal=signal,
        )

        new_cash = snapshot.cash - cost
        new_positions = snapshot.positions + (position,)
        new_equity = new_cash + _positions_value(new_positions, {instrument: price})

        return replace(
            snapshot,
            cash=new_cash,
            positions=new_positions,
            equity=new_equity,
            peak_equity=max(snapshot.peak_equity, new_equity),
        )

    def close_position(
        self,
        snapshot: PortfolioSnapshot,
        instrument: str,
        price: Decimal,
        reason: str,
    ) -> PortfolioSnapshot:
        """Close a position by instrument, record the trade."""
        position = _find_position(snapshot.positions, instrument)
        if position is None:
            return snapshot

        pnl = _calc_pnl(position, price)
        pnl_pct = pnl / (position.entry_price * position.quantity)

        trade = Trade(
            instrument=instrument,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=price,
            entry_time=position.entry_time,
            exit_time=snapshot.timestamp,
            quantity=position.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            signal_type=position.signal.signal_type if position.signal else None,
            exit_reason=reason,
        )

        proceeds = price * position.quantity
        new_cash = snapshot.cash + proceeds
        new_positions = tuple(p for p in snapshot.positions if p.instrument != instrument)
        new_trades = snapshot.trades + (trade,)
        new_equity = new_cash + _positions_value(new_positions, {})

        return replace(
            snapshot,
            cash=new_cash,
            positions=new_positions,
            trades=new_trades,
            equity=new_equity,
            peak_equity=max(snapshot.peak_equity, new_equity),
            drawdown=_calc_drawdown(max(snapshot.peak_equity, new_equity), new_equity),
        )

    def update_equity(
        self,
        snapshot: PortfolioSnapshot,
        prices: dict[str, Decimal],
    ) -> PortfolioSnapshot:
        """Recompute equity from current market prices."""
        new_equity = snapshot.cash + _positions_value(snapshot.positions, prices)
        new_peak = max(snapshot.peak_equity, new_equity)

        return replace(
            snapshot,
            equity=new_equity,
            peak_equity=new_peak,
            drawdown=_calc_drawdown(new_peak, new_equity),
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _find_position(
    positions: tuple[Position, ...], instrument: str
) -> Position | None:
    for p in positions:
        if p.instrument == instrument:
            return p
    return None


def _calc_pnl(position: Position, exit_price: Decimal) -> Decimal:
    diff = exit_price - position.entry_price
    if position.direction == Direction.DOWN:
        diff = -diff
    return diff * position.quantity


def _positions_value(
    positions: tuple[Position, ...], prices: dict[str, Decimal]
) -> Decimal:
    total = Decimal("0")
    for p in positions:
        price = prices.get(p.instrument, p.entry_price)
        total += price * p.quantity
    return total


def _calc_drawdown(peak: Decimal, equity: Decimal) -> Decimal:
    if peak == Decimal("0"):
        return Decimal("0")
    return (peak - equity) / peak
