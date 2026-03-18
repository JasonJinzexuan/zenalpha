"""Market Regime Detection (v2.2).

Multi-indicator regime classification using VIX, credit spread, MOVE index,
market breadth, and sector rotation.  Outputs a MarketRegime enum used by
the L9 scorer to dynamically adjust timeframe weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from chanquant.core.objects import MarketRegime, TimeFrame

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class RegimeInputs:
    """Raw market indicators fed into the regime detector."""

    vix: Decimal = Decimal("20")
    credit_spread_bp: Decimal = Decimal("200")  # HY-IG OAS in basis points
    move_index: Decimal = Decimal("80")
    breadth_pct: Decimal = Decimal("55")  # % of S&P 500 above 200-day MA
    sector_rotation_ratio: Decimal = Decimal("1.0")  # XLK / XLU


# ── Score normalisation functions ────────────────────────────────────────────

def _vix_score(vix: Decimal) -> Decimal:
    """0 = calm, 1 = extreme."""
    if vix < Decimal("15"):
        return Decimal("0.1")
    if vix < Decimal("25"):
        return Decimal("0.3")
    if vix < Decimal("40"):
        return Decimal("0.6")
    return Decimal("1.0")


def _credit_score(spread_bp: Decimal) -> Decimal:
    if spread_bp < Decimal("300"):
        return Decimal("0.1")
    if spread_bp < Decimal("500"):
        return Decimal("0.5")
    return Decimal("1.0")


def _move_score(move: Decimal) -> Decimal:
    if move < Decimal("100"):
        return Decimal("0.1")
    if move < Decimal("150"):
        return Decimal("0.5")
    return Decimal("1.0")


def _breadth_score(pct: Decimal) -> Decimal:
    """Lower breadth = higher stress."""
    if pct > Decimal("60"):
        return Decimal("0.1")
    if pct > Decimal("40"):
        return Decimal("0.4")
    return Decimal("0.9")


def _rotation_score(ratio: Decimal) -> Decimal:
    """Lower XLK/XLU = risk-off = higher stress."""
    if ratio > Decimal("1.5"):
        return Decimal("0.1")
    if ratio > Decimal("1.0"):
        return Decimal("0.3")
    if ratio > Decimal("0.7"):
        return Decimal("0.6")
    return Decimal("0.9")


# ── Regime weight adjustments ────────────────────────────────────────────────

# Per-regime adjustments to timeframe weights used by L9 scorer.
_REGIME_TF_ADJUSTMENTS: dict[MarketRegime, dict[TimeFrame, Decimal]] = {
    MarketRegime.LOW_VOL: {
        TimeFrame.MIN_1: Decimal("0.5"),
        TimeFrame.MIN_5: Decimal("0.8"),
    },
    MarketRegime.NORMAL: {},
    MarketRegime.HIGH_VOL: {
        TimeFrame.MIN_1: Decimal("0.3"),
        TimeFrame.MIN_5: Decimal("0.5"),
    },
    MarketRegime.EXTREME: {
        TimeFrame.MIN_1: Decimal("0"),
        TimeFrame.MIN_5: Decimal("0"),
        TimeFrame.MIN_30: Decimal("0"),
        TimeFrame.HOUR_1: Decimal("0"),
        TimeFrame.DAILY: Decimal("0.5"),
    },
}


class RegimeDetector:
    """Classify the current market environment into one of four regimes."""

    # Component weights for composite score.
    _WEIGHTS = {
        "vix": Decimal("0.30"),
        "credit": Decimal("0.25"),
        "move": Decimal("0.15"),
        "breadth": Decimal("0.20"),
        "rotation": Decimal("0.10"),
    }

    def detect(self, inputs: RegimeInputs) -> MarketRegime:
        composite = (
            _vix_score(inputs.vix) * self._WEIGHTS["vix"]
            + _credit_score(inputs.credit_spread_bp) * self._WEIGHTS["credit"]
            + _move_score(inputs.move_index) * self._WEIGHTS["move"]
            + _breadth_score(inputs.breadth_pct) * self._WEIGHTS["breadth"]
            + _rotation_score(inputs.sector_rotation_ratio) * self._WEIGHTS["rotation"]
        )
        if composite < Decimal("0.3"):
            return MarketRegime.LOW_VOL
        if composite < Decimal("0.6"):
            return MarketRegime.NORMAL
        if composite < Decimal("0.8"):
            return MarketRegime.HIGH_VOL
        return MarketRegime.EXTREME

    def adjust_timeframe_weight(
        self,
        regime: MarketRegime,
        base_weight: Decimal,
        timeframe: TimeFrame,
    ) -> Decimal:
        """Apply regime-specific multiplier to a timeframe weight."""
        adjustments = _REGIME_TF_ADJUSTMENTS.get(regime, {})
        multiplier = adjustments.get(timeframe, _ONE)
        return base_weight * multiplier
