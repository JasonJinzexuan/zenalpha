"""Risk Manager — single gate composing all risk checks.

Evaluates: conflicts → regime → drawdown → position sizing → constraints.
Returns RiskCheckResult: approved or rejected with reason.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from chanquant.execution.position import (
    PositionSizer,
    atr as calc_atr,
    check_portfolio_drawdown,
)
from chanquant.risk.conflict import resolve_conflicts
from chanquant.risk.models import RiskCheckResult
from chanquant.scoring.regime import RegimeDetector, RegimeInputs
from chanquant.strategy.models import RiskParams

_ZERO = Decimal("0")


class RiskManager:
    """Compose all risk checks into a single evaluate() call."""

    def __init__(self) -> None:
        self._sizer = PositionSizer()
        self._regime_detector = RegimeDetector()

    def evaluate(
        self,
        nesting_result: dict[str, Any],
        params: RiskParams,
        equity: Decimal = Decimal("1000000"),
        current_positions: int = 0,
        current_drawdown: Decimal = _ZERO,
        atr_value: Decimal = _ZERO,
        current_price: Decimal = _ZERO,
        regime_inputs: RegimeInputs | None = None,
    ) -> RiskCheckResult:
        """Pure risk checks only. Signal quality is LLM's job.

        Only blocks trades for capital-protection reasons:
        - Extreme market regime
        - Drawdown limits breached
        - Max positions reached
        Calculates position sizing when approved.
        """
        # Collect signal context (for informational purposes, not blocking)
        per_level = nesting_result.get("per_level", {})
        conflict = resolve_conflicts(per_level)

        # 1. Market regime filter — extreme conditions, hard stop
        regime_str = "NORMAL"
        if regime_inputs is not None:
            regime = self._regime_detector.detect(regime_inputs)
            regime_str = regime.name
            if regime_str in params.regime_filter:
                return RiskCheckResult(
                    approved=False,
                    reason=f"市场环境 {regime_str} 已被策略过滤",
                    regime=regime_str,
                    conflicts=conflict.conflicts,
                )

        # 2. Drawdown check — protect capital
        dd_action = check_portfolio_drawdown(current_drawdown)
        if dd_action == "suspend":
            return RiskCheckResult(
                approved=False,
                reason=f"回撤 {current_drawdown:.1%} 触发暂停线",
                drawdown_status="suspend",
                regime=regime_str,
                conflicts=conflict.conflicts,
            )
        if dd_action == "clear_all":
            return RiskCheckResult(
                approved=False,
                reason=f"回撤 {current_drawdown:.1%} 触发清仓线",
                drawdown_status="clear",
                regime=regime_str,
                conflicts=conflict.conflicts,
            )

        dd_status = "ok"
        position_scale = Decimal("1.0")
        if dd_action == "half_all":
            dd_status = "half"
            position_scale = Decimal("0.5")

        # 3. Max concurrent positions — capital allocation limit
        if current_positions >= params.max_concurrent_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"持仓数已达上限: {current_positions}/{params.max_concurrent_positions}",
                regime=regime_str,
                drawdown_status=dd_status,
                conflicts=conflict.conflicts,
            )

        # 4. Position sizing
        if params.use_atr_sizing and atr_value > _ZERO and current_price > _ZERO:
            stop_distance = atr_value * params.stop_loss_atr_mult
            risk_per_trade = equity * Decimal("0.01")  # risk 1% per trade
            raw_shares = risk_per_trade / stop_distance
            raw_pct = (raw_shares * current_price) / equity if equity > _ZERO else _ZERO
            position_pct = min(raw_pct, params.max_position_pct) * position_scale
        else:
            position_pct = params.max_position_pct * position_scale

        return RiskCheckResult(
            approved=True,
            adjusted_position_pct=position_pct,
            regime=regime_str,
            drawdown_status=dd_status,
            conflicts=conflict.conflicts,
        )
