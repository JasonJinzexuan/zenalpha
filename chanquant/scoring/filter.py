"""Signal filter for the L9 scoring pipeline."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import ScanResult, SignalType

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
    """Filter and rank scan results based on quality thresholds."""

    def __init__(
        self,
        min_trend_alignment: Decimal = _MIN_TREND_ALIGNMENT,
        min_divergence_strength: Decimal = _MIN_DIVERGENCE_STRENGTH,
        max_signal_freshness: int = _MAX_SIGNAL_FRESHNESS,
        min_nesting_depth: int = _MIN_NESTING_DEPTH,
    ) -> None:
        self._min_trend_alignment = min_trend_alignment
        self._min_divergence_strength = min_divergence_strength
        self._max_signal_freshness = max_signal_freshness
        self._min_nesting_depth = min_nesting_depth

    def filter(
        self,
        results: Sequence[ScanResult],
    ) -> Sequence[ScanResult]:
        passed = [r for r in results if self._passes(r)]
        sorted_results = sorted(passed, key=_sort_key)
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
