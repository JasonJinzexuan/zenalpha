"""L7: Signal generation (买卖点).

Generates B1/S1, B2/S2, B3/S3 buy/sell signals from trend, divergence, and centers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import (
    Center,
    Direction,
    Divergence,
    DivergenceType,
    Segment,
    Signal,
    SignalType,
    Stroke,
    TrendClass,
    TrendType,
)


_ZERO = Decimal("0")


# ── B1/S1: Trend Divergence Reversal ────────────────────────────────────────


def _generate_b1_s1(
    trend: TrendType,
    divergence: Divergence,
    instrument: str,
) -> list[Signal]:
    """B1/S1: trend divergence → reversal signal."""
    if divergence.type != DivergenceType.TREND:
        return []

    seg_c = divergence.segment_c
    if seg_c.end_time is None:
        return []

    if trend.classification == TrendClass.DOWN_TREND:
        return [Signal(
            signal_type=SignalType.B1,
            level=trend.level,
            instrument=instrument,
            timestamp=seg_c.end_time,
            price=seg_c.low,
            divergence=divergence,
            strength=divergence.strength,
            source_lesson="L7.1",
            reasoning="下跌趋势背驰，产生第一类买点",
        )]

    if trend.classification == TrendClass.UP_TREND:
        return [Signal(
            signal_type=SignalType.S1,
            level=trend.level,
            instrument=instrument,
            timestamp=seg_c.end_time,
            price=seg_c.high,
            divergence=divergence,
            strength=divergence.strength,
            source_lesson="L7.1",
            reasoning="上涨趋势背驰，产生第一类卖点",
        )]

    return []


# ── B2/S2: Second Buy/Sell Point ────────────────────────────────────────────


def _check_no_new_low(
    segments: Sequence[Segment], reference_low: Decimal
) -> bool:
    """After B1, check if price makes no new low."""
    if not segments:
        return False
    recent = segments[-1]
    return recent.low >= reference_low


def _check_no_new_high(
    segments: Sequence[Segment], reference_high: Decimal
) -> bool:
    """After S1, check if price makes no new high."""
    if not segments:
        return False
    recent = segments[-1]
    return recent.high <= reference_high


def _check_small_to_large(
    seg: Segment, center: Center | None
) -> bool:
    """Check if a small-level structure completes inside a larger center."""
    if center is None or seg.end_time is None:
        return False
    if center.start_time and center.end_time:
        return (
            seg.end_time >= center.start_time
            and seg.end_time <= center.end_time
        )
    return False


def _generate_b2_s2(
    trend: TrendType,
    divergence: Divergence | None,
    segments: Sequence[Segment],
    centers: Sequence[Center],
    prior_signals: list[Signal],
    instrument: str,
) -> list[Signal]:
    """B2/S2: no new low after B1, OR consolidation divergence, OR small-to-large."""
    signals: list[Signal] = []

    # Find prior B1/S1
    b1_signals = [s for s in prior_signals if s.signal_type == SignalType.B1]
    s1_signals = [s for s in prior_signals if s.signal_type == SignalType.S1]

    # B2 after B1
    for b1 in b1_signals:
        if _check_no_new_low(segments, b1.price):
            seg = segments[-1] if segments else None
            if seg and seg.end_time:
                signals.append(Signal(
                    signal_type=SignalType.B2,
                    level=trend.level,
                    instrument=instrument,
                    timestamp=seg.end_time,
                    price=seg.low,
                    divergence=divergence,
                    strength=Decimal("0.7"),
                    source_lesson="L7.2",
                    reasoning="B1后不创新低，产生第二类买点",
                ))

    # S2 after S1
    for s1 in s1_signals:
        if _check_no_new_high(segments, s1.price):
            seg = segments[-1] if segments else None
            if seg and seg.end_time:
                signals.append(Signal(
                    signal_type=SignalType.S2,
                    level=trend.level,
                    instrument=instrument,
                    timestamp=seg.end_time,
                    price=seg.high,
                    divergence=divergence,
                    strength=Decimal("0.7"),
                    source_lesson="L7.2",
                    reasoning="S1后不创新高，产生第二类卖点",
                ))

    # Consolidation divergence
    if divergence and divergence.type == DivergenceType.CONSOLIDATION:
        seg_c = divergence.segment_c
        if seg_c.end_time:
            if seg_c.direction == Direction.DOWN:
                signals.append(Signal(
                    signal_type=SignalType.B2,
                    level=trend.level,
                    instrument=instrument,
                    timestamp=seg_c.end_time,
                    price=seg_c.low,
                    divergence=divergence,
                    strength=divergence.strength,
                    source_lesson="L7.2",
                    reasoning="盘整背驰，产生第二类买点",
                ))
            else:
                signals.append(Signal(
                    signal_type=SignalType.S2,
                    level=trend.level,
                    instrument=instrument,
                    timestamp=seg_c.end_time,
                    price=seg_c.high,
                    divergence=divergence,
                    strength=divergence.strength,
                    source_lesson="L7.2",
                    reasoning="盘整背驰，产生第二类卖点",
                ))

    # Small-to-large
    if segments and centers:
        last_seg = segments[-1]
        if _check_small_to_large(last_seg, centers[-1]):
            if last_seg.end_time:
                sig_type = SignalType.B2 if last_seg.direction == Direction.DOWN else SignalType.S2
                price = last_seg.low if last_seg.direction == Direction.DOWN else last_seg.high
                signals.append(Signal(
                    signal_type=sig_type,
                    level=trend.level,
                    instrument=instrument,
                    timestamp=last_seg.end_time,
                    price=price,
                    small_to_large=True,
                    strength=Decimal("0.6"),
                    source_lesson="L7.2",
                    reasoning="小转大，产生第二类买卖点",
                ))

    return signals


# ── B3/S3: Third Buy/Sell Point ─────────────────────────────────────────────


def _generate_b3_s3(
    centers: Sequence[Center],
    strokes: Sequence[Stroke],
    instrument: str,
    level: TrendType,
) -> list[Signal]:
    """B3/S3: break above ZG then pullback stays above ZG (first pullback only)."""
    signals: list[Signal] = []

    if not centers or len(strokes) < 2:
        return signals

    center = centers[-1]

    # Check strokes for center breakout + pullback pattern
    for i in range(len(strokes) - 1):
        curr = strokes[i]
        nxt = strokes[i + 1]

        # B3: break above ZG, then pullback low stays above ZG
        if (
            curr.direction == Direction.UP
            and curr.high > center.zg
            and nxt.direction == Direction.DOWN
            and nxt.low >= center.zg
            and nxt.end_time
        ):
            signals.append(Signal(
                signal_type=SignalType.B3,
                level=level.level,
                instrument=instrument,
                timestamp=nxt.end_time,
                price=nxt.low,
                center=center,
                strength=Decimal("0.5"),
                source_lesson="L7.3",
                reasoning="突破中枢上沿后回踩不破，产生第三类买点",
            ))

        # S3: break below ZD, then pullback high stays below ZD
        if (
            curr.direction == Direction.DOWN
            and curr.low < center.zd
            and nxt.direction == Direction.UP
            and nxt.high <= center.zd
            and nxt.end_time
        ):
            signals.append(Signal(
                signal_type=SignalType.S3,
                level=level.level,
                instrument=instrument,
                timestamp=nxt.end_time,
                price=nxt.high,
                center=center,
                strength=Decimal("0.5"),
                source_lesson="L7.3",
                reasoning="跌破中枢下沿后反弹不回，产生第三类卖点",
            ))

    return signals


# ── Public API ──────────────────────────────────────────────────────────────


class SignalGenerator:
    """Generates buy/sell signals from trend analysis results."""

    def generate(
        self,
        trend: TrendType,
        divergence: Divergence | None,
        centers: Sequence[Center],
        segments: Sequence[Segment],
        strokes: Sequence[Stroke],
        instrument: str = "",
    ) -> list[Signal]:
        """Generate all applicable signals."""
        signals: list[Signal] = []

        # B1/S1: trend divergence
        if divergence is not None:
            signals.extend(_generate_b1_s1(trend, divergence, instrument))

        # B2/S2: second buy/sell
        signals.extend(
            _generate_b2_s2(
                trend, divergence, segments, centers, signals, instrument
            )
        )

        # B3/S3: third buy/sell
        signals.extend(
            _generate_b3_s3(centers, strokes, instrument, trend)
        )

        return signals
