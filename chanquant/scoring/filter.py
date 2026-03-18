"""Signal filter for the L9 scoring pipeline.

Integrates market regime detection and event calendar filtering.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import MarketRegime, ScanResult, SignalType
from chanquant.scoring.event_calendar import EventCalendar
from chanquant.scoring.regime import RegimeDetector, RegimeInputs

_SIGNAL_PRIORITY: dict[SignalType, int] = {
    SignalType.B1: 0,
    SignalType.S1: 0,
    SignalType.B3: 1,
    SignalType.S3: 1,
    SignalType.B2: 2,
    SignalType.S2: 2,
}

_MIN_TREND_ALIGNMENT = Decimal("2")
_MIN_DIVERGENCE_STRENGTH = Decimal("0.3")
_MAX_SIGNAL_FRESHNESS = 3
_MIN_NESTING_DEPTH = 2


class SignalFilter:
    """Filter and rank scan results based on quality thresholds.

    Optionally applies market regime adjustments and event calendar filtering.
    """

    def __init__(
        self,
        min_trend_alignment: Decimal = _MIN_TREND_ALIGNMENT,
        min_divergence_strength: Decimal = _MIN_DIVERGENCE_STRENGTH,
        max_signal_freshness: int = _MAX_SIGNAL_FRESHNESS,
        min_nesting_depth: int = _MIN_NESTING_DEPTH,
        event_calendar: EventCalendar | None = None,
        regime: MarketRegime | None = None,
    ) -> None:
        self._min_trend_alignment = min_trend_alignment
        self._min_divergence_strength = min_divergence_strength
        self._max_signal_freshness = max_signal_freshness
        self._min_nesting_depth = min_nesting_depth
        self._event_calendar = event_calendar
        self._regime = regime

    def filter(
        self,
        results: Sequence[ScanResult],
        current_time: datetime | None = None,
    ) -> Sequence[ScanResult]:
        passed: list[ScanResult] = []
        for r in results:
            if not self._passes(r):
                continue
            # Apply event calendar score adjustment
            adjusted = self._apply_event_adjustment(r, current_time)
            if adjusted is None:
                continue
            passed.append(adjusted)

        sorted_results = sorted(passed, key=_sort_key)
        return tuple(
            replace(r, rank=idx + 1)
            for idx, r in enumerate(sorted_results)
        )

    def _passes(self, result: ScanResult) -> bool:
        if not _check_divergence_strength(
            result, self._min_divergence_strength
        ):
            return False
        if not _check_trend_alignment(result, self._min_trend_alignment):
            return False
        if not _check_nesting_depth(result, self._min_nesting_depth):
            return False
        return True

    def _apply_event_adjustment(
        self,
        result: ScanResult,
        current_time: datetime | None,
    ) -> ScanResult | None:
        """Apply event calendar multiplier; returns None if signal blocked."""
        if self._event_calendar is None or current_time is None:
            return result
        multiplier = self._event_calendar.score_multiplier(
            result.signal, current_time
        )
        if multiplier <= Decimal("0"):
            return None
        if multiplier < Decimal("1"):
            adjusted_score = result.score * multiplier
            return replace(result, score=adjusted_score)
        return result


def _check_divergence_strength(
    result: ScanResult,
    threshold: Decimal,
) -> bool:
    sig = result.signal
    if sig.divergence is None:
        return False
    return sig.divergence.area_ratio >= threshold


def _check_trend_alignment(
    result: ScanResult,
    threshold: Decimal,
) -> bool:
    nesting = result.nesting
    if nesting is None:
        return True
    if nesting.direction_aligned:
        alignment = Decimal("3")
    elif nesting.nesting_depth >= 2:
        alignment = Decimal("2")
    else:
        alignment = Decimal("1")
    return alignment >= threshold


def _check_nesting_depth(
    result: ScanResult,
    min_depth: int,
) -> bool:
    nesting = result.nesting
    if nesting is None:
        return True
    return nesting.nesting_depth >= min_depth


def _sort_key(result: ScanResult) -> tuple[Decimal, int]:
    priority = _SIGNAL_PRIORITY.get(result.signal.signal_type, 9)
    return (-result.score, priority)
