"""L9 signal scoring engine for 缠论 quantitative analysis."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import (
    DivergenceType,
    IntervalNesting,
    MarketRegime,
    ScanResult,
    Signal,
    SignalType,
    TimeFrame,
)
from chanquant.scoring.regime import RegimeDetector

_SIGNAL_TYPE_SCORES: dict[SignalType, Decimal] = {
    SignalType.B1: Decimal("5"),
    SignalType.B2: Decimal("4"),
    SignalType.B3: Decimal("5"),
    SignalType.S1: Decimal("5"),
    SignalType.S2: Decimal("4"),
    SignalType.S3: Decimal("5"),
}

_TIMEFRAME_WEIGHTS: dict[TimeFrame, Decimal] = {
    TimeFrame.MONTHLY: Decimal("8"),
    TimeFrame.WEEKLY: Decimal("5"),
    TimeFrame.DAILY: Decimal("3"),
    TimeFrame.HOUR_1: Decimal("2"),
    TimeFrame.MIN_30: Decimal("2"),
    TimeFrame.MIN_5: Decimal("1"),
    TimeFrame.MIN_1: Decimal("1"),
}


class SignalScorer:
    """Score signals based on the L9 composite formula.

    Optionally accepts a MarketRegime to dynamically adjust timeframe weights.
    """

    def __init__(self, regime: MarketRegime | None = None) -> None:
        self._regime = regime
        self._regime_detector = RegimeDetector() if regime is not None else None

    def score(
        self,
        signal: Signal,
        nesting: IntervalNesting | None = None,
    ) -> ScanResult:
        signal_score = _SIGNAL_TYPE_SCORES.get(
            signal.signal_type, Decimal("1")
        )
        base_tf_weight = _TIMEFRAME_WEIGHTS.get(
            signal.level, Decimal("1")
        )
        # Apply regime adjustment to timeframe weight
        if self._regime is not None and self._regime_detector is not None:
            timeframe_weight = self._regime_detector.adjust_timeframe_weight(
                self._regime, base_tf_weight, signal.level,
            )
        else:
            timeframe_weight = base_tf_weight
        div_strength = _divergence_strength(signal)
        trend_align = _trend_alignment(signal, nesting)
        vol_factor = _volume_factor(signal)

        composite = (
            signal_score
            * timeframe_weight
            * div_strength
            * trend_align
            * vol_factor
        )

        return ScanResult(
            instrument=signal.instrument,
            signal=signal,
            nesting=nesting,
            score=composite,
            rank=0,
            scan_time=datetime.now(),
        )

    def score_batch(
        self,
        signals: Sequence[tuple[Signal, IntervalNesting | None]],
    ) -> Sequence[ScanResult]:
        results = [self.score(sig, nest) for sig, nest in signals]
        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
        return tuple(
            ScanResult(
                instrument=r.instrument,
                signal=r.signal,
                nesting=r.nesting,
                score=r.score,
                rank=idx + 1,
                scan_time=r.scan_time,
            )
            for idx, r in enumerate(sorted_results)
        )


def _divergence_strength(signal: Signal) -> Decimal:
    if signal.divergence is None:
        return Decimal("0.5")
    a_area = abs(signal.divergence.a_macd_area)
    c_area = abs(signal.divergence.c_macd_area)
    if a_area == Decimal("0"):
        return Decimal("0.5")
    strength = Decimal("1") - c_area / a_area
    return max(Decimal("0"), min(Decimal("1"), strength))


def _trend_alignment(
    signal: Signal,
    nesting: IntervalNesting | None,
) -> Decimal:
    if nesting is None:
        return Decimal("2")
    if nesting.direction_aligned:
        return Decimal("3")
    if nesting.nesting_depth >= 2:
        return Decimal("2")
    return Decimal("1")


def _volume_factor(signal: Signal) -> Decimal:
    if signal.divergence is None:
        return Decimal("1")
    vol_ratio = signal.divergence.volume_ratio
    if vol_ratio is None:
        return Decimal("1")
    if signal.divergence.type == DivergenceType.TREND:
        if vol_ratio < Decimal("0.7"):
            return Decimal("1.3")
        if vol_ratio > Decimal("1.3"):
            return Decimal("0.7")
        return Decimal("1")
    # Consolidation divergence
    if vol_ratio > Decimal("1.5"):
        return Decimal("1.5")
    if vol_ratio < Decimal("0.5"):
        return Decimal("0.5")
    return Decimal("1")
