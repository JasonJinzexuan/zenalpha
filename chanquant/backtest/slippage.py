"""Slippage and commission model for realistic execution simulation.

All calculations use Decimal. Returns adjusted execution prices that are
always worse than the ideal price.
"""

from __future__ import annotations

from decimal import Decimal

from chanquant.core.objects import Direction

# Slippage basis points by market cap tier
_SLIPPAGE_BPS: dict[str, Decimal] = {
    "large_cap": Decimal("0.0001"),   # 0.01%
    "mid_cap": Decimal("0.0003"),     # 0.03%
    "small_cap": Decimal("0.0005"),   # 0.05%
}

_COMMISSION_PER_SHARE = Decimal("0.005")
_MIN_COMMISSION = Decimal("1")


class SlippageModel:
    """Compute realistic execution price including slippage, market impact,
    and commission."""

    def apply(
        self,
        price: Decimal,
        direction: Direction,
        volume: int,
        market_cap_tier: str,
        avg_volume: int = 1_000_000,
        volatility: Decimal = Decimal("0.02"),
    ) -> Decimal:
        """Return adjusted execution price (always worse than ideal).

        Components:
        - Base slippage: tier-based percentage
        - Market impact: sqrt(order_qty / avg_volume) * volatility * price
        - Commission: $0.005/share, min $1 — folded into price
        """
        base_slip = _base_slippage(price, market_cap_tier)
        impact = _market_impact(price, volume, avg_volume, volatility)
        commission = _commission_per_unit(volume)

        total_adjustment = base_slip + impact + commission

        if direction == Direction.UP:
            return price + total_adjustment  # buying: pay more
        return price - total_adjustment  # selling: receive less

    def commission(self, quantity: Decimal) -> Decimal:
        """Compute raw commission for a given share quantity."""
        raw = quantity * _COMMISSION_PER_SHARE
        return max(raw, _MIN_COMMISSION)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _base_slippage(price: Decimal, tier: str) -> Decimal:
    bps = _SLIPPAGE_BPS.get(tier, _SLIPPAGE_BPS["mid_cap"])
    return price * bps


def _market_impact(
    price: Decimal,
    order_qty: int,
    avg_volume: int,
    volatility: Decimal,
) -> Decimal:
    if avg_volume <= 0:
        return Decimal("0")
    ratio = Decimal(order_qty) / Decimal(avg_volume)
    sqrt_ratio = _decimal_sqrt(ratio)
    return sqrt_ratio * volatility * price


def _commission_per_unit(quantity: int) -> Decimal:
    """Commission cost spread per share."""
    if quantity <= 0:
        return Decimal("0")
    total = max(Decimal(quantity) * _COMMISSION_PER_SHARE, _MIN_COMMISSION)
    return total / Decimal(quantity)


def _decimal_sqrt(value: Decimal) -> Decimal:
    """Integer-arithmetic square root for Decimal (Newton's method)."""
    if value <= Decimal("0"):
        return Decimal("0")
    # Use sufficient precision
    guess = value
    for _ in range(50):
        next_guess = (guess + value / guess) / Decimal("2")
        if abs(next_guess - guess) < Decimal("1E-20"):
            break
        guess = next_guess
    return guess
