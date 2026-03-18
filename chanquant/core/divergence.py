"""L6: Divergence detection (背驰检测).

Compares MACD areas between segments a and c for trend and consolidation divergence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import (
    Center,
    Divergence,
    DivergenceType,
    MACDValue,
    Segment,
    TrendClass,
    TrendType,
    TimeFrame,
)


_ZERO = Decimal("0")
_ONE = Decimal("1")
_NEAR_ZERO_THRESHOLD = Decimal("0.05")
_STAGNATION_RATIO = Decimal("0.8")


# ── MACD Area Calculation ───────────────────────────────────────────────────


def _segment_macd_area(
    segment: Segment,
    macd_values: Sequence[MACDValue],
) -> Decimal:
    """Calculate MACD histogram area for a segment.

    Uses the segment's own macd_area if available, otherwise sums from values.
    """
    if segment.macd_area != _ZERO:
        return abs(segment.macd_area)

    # Fallback: sum histogram values over segment strokes
    total = _ZERO
    for stroke in segment.strokes:
        total += abs(stroke.macd_area)
    return total


def _segment_dif_peak(
    segment: Segment,
    macd_values: Sequence[MACDValue],
) -> Decimal:
    """Find the peak DIF value within a segment's strokes."""
    peak = _ZERO
    for stroke in segment.strokes:
        candidate = max(abs(stroke.macd_dif_start), abs(stroke.macd_dif_end))
        if candidate > peak:
            peak = candidate
    return peak


# ── MACD Near Zero Check ────────────────────────────────────────────────────


def _macd_returns_near_zero(
    macd_values: Sequence[MACDValue],
    center: Center | None,
) -> bool:
    """Check if MACD histogram returns near zero around a center."""
    if center is None or not macd_values:
        return False

    # Find MACD values that correspond to the center's time range
    for val in macd_values:
        if abs(val.histogram) < _NEAR_ZERO_THRESHOLD:
            return True
    return False


# ── Divergence Confirmation ─────────────────────────────────────────────────


def _check_area_divergence(a_area: Decimal, c_area: Decimal) -> bool:
    """Area divergence: c area < a area."""
    return c_area < a_area and a_area > _ZERO


def _check_dif_divergence(a_dif: Decimal, c_dif: Decimal) -> bool:
    """DIF peak divergence: c peak < a peak."""
    return c_dif < a_dif and a_dif > _ZERO


def _check_stagnation(a_area: Decimal, c_area: Decimal) -> bool:
    """Stagnation: c area is very small relative to a."""
    if a_area <= _ZERO:
        return False
    ratio = c_area / a_area
    return ratio < _STAGNATION_RATIO


def _count_confirmations(
    a_area: Decimal,
    c_area: Decimal,
    a_dif: Decimal,
    c_dif: Decimal,
) -> int:
    """Count how many divergence confirmations are met (need >= 2 of 3)."""
    count = 0
    if _check_area_divergence(a_area, c_area):
        count += 1
    if _check_dif_divergence(a_dif, c_dif):
        count += 1
    if _check_stagnation(a_area, c_area):
        count += 1
    return count


def _calc_strength(a_area: Decimal, c_area: Decimal) -> Decimal:
    """Strength = 1 - c_area / a_area."""
    if a_area <= _ZERO:
        return _ZERO
    return _ONE - c_area / a_area


# ── Contains B3 Check ───────────────────────────────────────────────────────


def _segment_c_contains_b3(seg_c: Segment, center_b: Center | None) -> bool:
    """Check if segment c contains a B3-type structure (break and pullback)."""
    if center_b is None:
        return False

    for stroke in seg_c.strokes:
        # Stroke breaks above ZG then comes back
        if stroke.high > center_b.zg and stroke.low >= center_b.zg:
            return True
        # Stroke breaks below ZD then comes back
        if stroke.low < center_b.zd and stroke.high <= center_b.zd:
            return True
    return False


# ── Trend Divergence ────────────────────────────────────────────────────────


def _detect_trend_divergence(
    trend: TrendType,
    macd_values: Sequence[MACDValue],
) -> Divergence | None:
    """Detect trend divergence by comparing a vs c MACD areas."""
    seg_a = trend.segment_a
    seg_c = trend.segment_c
    if seg_a is None or seg_c is None:
        return None

    a_area = _segment_macd_area(seg_a, macd_values)
    c_area = _segment_macd_area(seg_c, macd_values)
    a_dif = _segment_dif_peak(seg_a, macd_values)
    c_dif = _segment_dif_peak(seg_c, macd_values)

    # Need at least 2 of 3 confirmations
    confirmations = _count_confirmations(a_area, c_area, a_dif, c_dif)
    if confirmations < 2:
        return None

    # MACD should return near zero at center B
    near_zero = _macd_returns_near_zero(macd_values, trend.center_b)
    if not near_zero:
        return None

    contains_b3 = _segment_c_contains_b3(seg_c, trend.center_b)

    return Divergence(
        type=DivergenceType.TREND,
        level=trend.level,
        trend_type=trend,
        segment_a=seg_a,
        segment_c=seg_c,
        a_macd_area=a_area,
        c_macd_area=c_area,
        a_dif_peak=a_dif,
        c_dif_peak=c_dif,
        c_contains_b3=contains_b3,
        strength=_calc_strength(a_area, c_area),
    )


# ── Consolidation Divergence ────────────────────────────────────────────────


def _detect_consolidation_divergence(
    trend: TrendType,
    macd_values: Sequence[MACDValue],
    segments: Sequence[Segment],
) -> Divergence | None:
    """Detect consolidation divergence by comparing same-direction exit segments."""
    if trend.center_a is None:
        return None

    center = trend.center_a
    # Find two same-direction segments exiting the center
    exit_segs: list[Segment] = []
    for seg in segments:
        if seg.start_time and center.end_time and seg.start_time >= center.end_time:
            exit_segs.append(seg)
    if len(exit_segs) < 2:
        return None

    # Compare first and last exit segments
    seg_a = exit_segs[0]
    seg_c = exit_segs[-1]

    if seg_a.direction != seg_c.direction:
        return None

    a_area = _segment_macd_area(seg_a, macd_values)
    c_area = _segment_macd_area(seg_c, macd_values)
    a_dif = _segment_dif_peak(seg_a, macd_values)
    c_dif = _segment_dif_peak(seg_c, macd_values)

    confirmations = _count_confirmations(a_area, c_area, a_dif, c_dif)
    if confirmations < 2:
        return None

    return Divergence(
        type=DivergenceType.CONSOLIDATION,
        level=trend.level,
        trend_type=trend,
        segment_a=seg_a,
        segment_c=seg_c,
        a_macd_area=a_area,
        c_macd_area=c_area,
        a_dif_peak=a_dif,
        c_dif_peak=c_dif,
        strength=_calc_strength(a_area, c_area),
    )


# ── Volume Ratio ────────────────────────────────────────────────────────────


def _calc_volume_ratio(seg_a: Segment, seg_c: Segment) -> Decimal | None:
    """Calculate volume ratio between segments a and c as auxiliary factor."""
    vol_a = sum(s.start_fractal.elements[0].volume for s in seg_a.strokes)
    vol_c = sum(s.start_fractal.elements[0].volume for s in seg_c.strokes)
    if vol_a == 0:
        return None
    return Decimal(str(vol_c)) / Decimal(str(vol_a))


# ── Public API ──────────────────────────────────────────────────────────────


class DivergenceDetector:
    """Detects divergence in trend and consolidation contexts."""

    def detect(
        self,
        trend: TrendType,
        macd_values: Sequence[MACDValue],
        segments: Sequence[Segment] = (),
    ) -> Divergence | None:
        """Detect divergence based on trend classification."""
        if trend.classification in (TrendClass.UP_TREND, TrendClass.DOWN_TREND):
            div = _detect_trend_divergence(trend, macd_values)
            if div is not None:
                vol = _calc_volume_ratio(div.segment_a, div.segment_c)
                if vol is not None:
                    return Divergence(
                        type=div.type,
                        level=div.level,
                        trend_type=div.trend_type,
                        segment_a=div.segment_a,
                        segment_c=div.segment_c,
                        a_macd_area=div.a_macd_area,
                        c_macd_area=div.c_macd_area,
                        a_dif_peak=div.a_dif_peak,
                        c_dif_peak=div.c_dif_peak,
                        c_contains_b3=div.c_contains_b3,
                        volume_ratio=vol,
                        strength=div.strength,
                    )
                return div

        if trend.classification == TrendClass.CONSOLIDATION:
            return _detect_consolidation_divergence(
                trend, macd_values, segments
            )

        return None
