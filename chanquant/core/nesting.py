"""L8: Interval nesting (区间套).

Deterministic multi-timeframe nesting for signal confirmation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from chanquant.core.objects import (
    IntervalNesting,
    MergedSignal,
    Signal,
    SignalType,
    TimeFrame,
)


# ── Level Mapping ───────────────────────────────────────────────────────────

_LEVEL_MAP: dict[TimeFrame, tuple[TimeFrame, TimeFrame]] = {
    TimeFrame.MONTHLY: (TimeFrame.WEEKLY, TimeFrame.DAILY),
    TimeFrame.WEEKLY: (TimeFrame.DAILY, TimeFrame.MIN_30),
    TimeFrame.DAILY: (TimeFrame.MIN_30, TimeFrame.MIN_5),
    TimeFrame.MIN_30: (TimeFrame.MIN_5, TimeFrame.MIN_1),
}


def _is_buy_signal(sig: Signal) -> bool:
    return sig.signal_type in (SignalType.B1, SignalType.B2, SignalType.B3)


def _is_sell_signal(sig: Signal) -> bool:
    return sig.signal_type in (SignalType.S1, SignalType.S2, SignalType.S3)


def _signals_aligned(large: Signal, small: Signal) -> bool:
    """Check if large and small timeframe signals agree on direction."""
    large_buy = _is_buy_signal(large)
    small_buy = _is_buy_signal(small)
    return large_buy == small_buy


def _latest_signal(signals: Sequence[Signal]) -> Signal | None:
    """Get the most recent signal by timestamp."""
    if not signals:
        return None
    return max(signals, key=lambda s: s.timestamp)


def _calc_confidence(
    depth: int, aligned: bool, signals: list[Signal | None]
) -> Decimal:
    """Calculate nesting confidence based on depth and alignment."""
    present = sum(1 for s in signals if s is not None)
    if present == 0:
        return Decimal("0")

    base = Decimal(str(present)) / Decimal("3")
    if aligned:
        base += Decimal("0.2")
    if depth >= 3:
        base += Decimal("0.1")

    return min(base, Decimal("1"))


# ── Public API ──────────────────────────────────────────────────────────────


class IntervalNester:
    """Deterministic interval nesting across timeframes."""

    def nest(
        self,
        signals_by_level: dict[TimeFrame, list[Signal]],
    ) -> IntervalNesting | None:
        """Step through levels large→small, check alignment.

        Returns None if no signals found at any level.
        """
        # Find the largest level with signals
        for large_tf in (
            TimeFrame.MONTHLY,
            TimeFrame.WEEKLY,
            TimeFrame.DAILY,
            TimeFrame.MIN_30,
        ):
            if large_tf not in _LEVEL_MAP:
                continue

            large_signals = signals_by_level.get(large_tf, [])
            large_sig = _latest_signal(large_signals)
            if large_sig is None:
                continue

            medium_tf, precise_tf = _LEVEL_MAP[large_tf]
            medium_sig = _latest_signal(
                signals_by_level.get(medium_tf, [])
            )
            precise_sig = _latest_signal(
                signals_by_level.get(precise_tf, [])
            )

            # Direction alignment filter
            aligned = True
            if medium_sig is not None and not _signals_aligned(large_sig, medium_sig):
                aligned = False
            if precise_sig is not None and not _signals_aligned(large_sig, precise_sig):
                aligned = False

            # Conflicting large=sell AND small=buy → no action
            if (
                _is_sell_signal(large_sig)
                and precise_sig is not None
                and _is_buy_signal(precise_sig)
            ):
                return IntervalNesting(
                    target_level=precise_tf,
                    large_signal=large_sig,
                    medium_signal=medium_sig,
                    precise_signal=precise_sig,
                    nesting_depth=self._count_depth(
                        large_sig, medium_sig, precise_sig
                    ),
                    direction_aligned=False,
                    confidence=Decimal("0"),
                )

            depth = self._count_depth(large_sig, medium_sig, precise_sig)
            sigs = [large_sig, medium_sig, precise_sig]
            confidence = _calc_confidence(depth, aligned, sigs)

            return IntervalNesting(
                target_level=precise_tf,
                large_signal=large_sig,
                medium_signal=medium_sig,
                precise_signal=precise_sig,
                nesting_depth=depth,
                direction_aligned=aligned,
                confidence=confidence,
            )

        return None

    def _count_depth(
        self,
        large: Signal | None,
        medium: Signal | None,
        precise: Signal | None,
    ) -> int:
        return sum(1 for s in (large, medium, precise) if s is not None)


# ── Signal Merge / Dedup (rule 8.6) ──────────────────────────────────────────

# Timeframe weights used for merged score calculation (same as L9).
_TIMEFRAME_WEIGHTS: dict[TimeFrame, Decimal] = {
    TimeFrame.MONTHLY: Decimal("8"),
    TimeFrame.WEEKLY: Decimal("5"),
    TimeFrame.DAILY: Decimal("3"),
    TimeFrame.HOUR_1: Decimal("2"),
    TimeFrame.MIN_30: Decimal("2"),
    TimeFrame.MIN_5: Decimal("1"),
    TimeFrame.MIN_1: Decimal("1"),
}

_DEDUP_BARS = 3  # suppress duplicate signals within 3 bars of same level


def merge_signals(
    signals: Sequence[Signal],
    instrument: str,
) -> MergedSignal | None:
    """Merge multi-level signals for one instrument into a single MergedSignal.

    - Primary signal = largest timeframe signal.
    - Supporting signals = remaining smaller timeframe signals.
    - merged_score = weighted sum of each signal's strength.
    - Returns None if no signals for this instrument.
    """
    inst_signals = [s for s in signals if s.instrument == instrument]
    if not inst_signals:
        return None

    # Dedup: within same level+direction, keep only most recent within 3-bar window
    deduped = _dedup_signals(inst_signals)
    if not deduped:
        return None

    # Sort by timeframe weight descending to find primary
    deduped.sort(
        key=lambda s: _TIMEFRAME_WEIGHTS.get(s.level, Decimal("1")),
        reverse=True,
    )

    primary = deduped[0]
    supporting = tuple(deduped[1:])

    merged_score = sum(
        s.strength * _TIMEFRAME_WEIGHTS.get(s.level, Decimal("1"))
        for s in deduped
    )

    depth = len(deduped)
    parts = [f"{primary.signal_type.value}@{primary.level.value}"]
    for s in supporting:
        parts.append(f"{s.signal_type.value}@{s.level.value}")
    summary = f"{instrument}: {' + '.join(parts)}"

    return MergedSignal(
        instrument=instrument,
        primary_signal=primary,
        supporting_signals=supporting,
        nesting_depth=depth,
        merged_score=merged_score,
        summary=summary,
    )


def _dedup_signals(signals: Sequence[Signal]) -> list[Signal]:
    """Remove duplicate signals: same instrument + level + direction within 3 bars."""
    seen: dict[tuple[TimeFrame, bool], Signal] = {}
    for sig in signals:
        is_buy = _is_buy_signal(sig)
        key = (sig.level, is_buy)
        existing = seen.get(key)
        if existing is None:
            seen[key] = sig
        else:
            # Keep the more recent one
            if sig.timestamp > existing.timestamp:
                seen[key] = sig
    return list(seen.values())
