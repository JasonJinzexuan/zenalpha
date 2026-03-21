"""Risk management data models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class RiskCheckResult(BaseModel, frozen=True):
    """Result of the risk gate evaluation."""

    approved: bool
    reason: str = ""
    adjusted_position_pct: Decimal = Decimal("0")
    regime: str = "NORMAL"
    conflicts: list[str] = Field(default_factory=list)
    drawdown_status: str = "ok"


class TradingInstruction(BaseModel, frozen=True):
    """Concrete trading instruction with numeric fields."""

    instrument: str
    action: str  # BUY | SELL | NO_ACTION
    strategy: str = ""
    entry_price: Decimal = Decimal("0")
    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal = Decimal("0")
    position_size_pct: Decimal = Decimal("0")
    position_shares: int = 0
    risk_reward_ratio: Decimal = Decimal("0")
    urgency: str = "WATCH"  # IMMEDIATE | WAIT_PULLBACK | WATCH
    confidence: Decimal = Decimal("0")
    signal_basis: str = ""
    risk_check: RiskCheckResult = RiskCheckResult(approved=False, reason="not evaluated")
    timestamp: str = ""
    # Collapsed detail
    nesting_summary: dict = Field(default_factory=dict)
    macro_context: str = ""
    reasoning: str = ""
