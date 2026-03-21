"""L7: Signal generation (买卖点).

Generates B1/S1, B2/S2, B3/S3 buy/sell signals from trend, divergence, and centers.
"""

from __future__ import annotations

from datetime import datetime
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


def _find_first_pullback_after(
    segments: Sequence[Segment],
    after_time: "datetime",
    direction: Direction,
) -> Segment | None:
    """Find the first pullback segment after a given time.

    For B2 (after B1 in downtrend): first DOWN segment after B1 timestamp.
    For S2 (after S1 in uptrend): first UP segment after S1 timestamp.
    """
    for seg in segments:
        if seg.start_time and seg.start_time > after_time and seg.direction == direction:
            return seg
    return None


def _generate_b2_s2(
    trend: TrendType,
    divergence: Divergence | None,
    segments: Sequence[Segment],
    centers: Sequence[Center],
    prior_signals: list[Signal],
    instrument: str,
) -> list[Signal]:
    """B2/S2: first pullback after B1 with no new low, OR consolidation divergence, OR small-to-large."""
    signals: list[Signal] = []

    # Find prior B1/S1
    b1_signals = [s for s in prior_signals if s.signal_type == SignalType.B1]
    s1_signals = [s for s in prior_signals if s.signal_type == SignalType.S1]

    # B2: first DOWN pullback after B1 that doesn't make new low
    for b1 in b1_signals:
        pullback = _find_first_pullback_after(segments, b1.timestamp, Direction.DOWN)
        if pullback and pullback.end_time and pullback.low >= b1.price:
            signals.append(Signal(
                signal_type=SignalType.B2,
                level=trend.level,
                instrument=instrument,
                timestamp=pullback.end_time,
                price=pullback.low,
                divergence=divergence,
                strength=Decimal("0.7"),
                source_lesson="L7.2",
                reasoning="B1后首次回调不创新低，产生第二类买点",
            ))

    # S2: first UP pullback after S1 that doesn't make new high
    for s1 in s1_signals:
        pullback = _find_first_pullback_after(segments, s1.timestamp, Direction.UP)
        if pullback and pullback.end_time and pullback.high <= s1.price:
            signals.append(Signal(
                signal_type=SignalType.S2,
                level=trend.level,
                instrument=instrument,
                timestamp=pullback.end_time,
                price=pullback.high,
                divergence=divergence,
                strength=Decimal("0.7"),
                source_lesson="L7.2",
                reasoning="S1后首次回调不创新高，产生第二类卖点",
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
    segments: Sequence[Segment],
    instrument: str,
    level: TrendType,
) -> list[Signal]:
    """B3/S3: segment breaks above ZG / below ZD, next segment pullback stays outside.

    Checks ALL centers (not just the last one), uses segments (not strokes)
    per Chan Theory: third buy/sell points are segment-level breakouts.
    Only generates one B3 and one S3 per center (first breakout only).
    """
    signals: list[Signal] = []

    if not centers or len(segments) < 2:
        return signals

    # Track which centers already have a B3 or S3 to enforce "first breakout only"
    b3_centers: set[int] = set()
    s3_centers: set[int] = set()

    for center_idx, center in enumerate(centers):
        for i in range(len(segments) - 1):
            curr = segments[i]
            nxt = segments[i + 1]

            # Only consider segments that start after the center formed
            if curr.start_time and center.end_time and curr.start_time < center.end_time:
                continue

            # B3: break above ZG, then pullback low stays strictly above ZG
            if (
                center_idx not in b3_centers
                and curr.direction == Direction.UP
                and curr.high > center.zg
                and nxt.direction == Direction.DOWN
                and nxt.low > center.zg
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
                b3_centers.add(center_idx)

            # S3: break below ZD, then pullback high stays strictly below ZD
            if (
                center_idx not in s3_centers
                and curr.direction == Direction.DOWN
                and curr.low < center.zd
                and nxt.direction == Direction.UP
                and nxt.high < center.zd
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
                s3_centers.add(center_idx)

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

        # B3/S3: third buy/sell (segment-level, all centers)
        signals.extend(
            _generate_b3_s3(centers, segments, instrument, trend)
        )

        return signals
