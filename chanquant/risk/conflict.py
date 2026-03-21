"""Signal conflict resolution.

Hard rules for handling contradictory buy/sell signals across timeframes.
"""

from __future__ import annotations

from dataclasses import dataclass


_BUY_TYPES = frozenset({"B1", "B2", "B3"})
_SELL_TYPES = frozenset({"S1", "S2", "S3"})


@dataclass(frozen=True)
class ConflictResult:
    """Outcome of conflict resolution."""

    has_conflict: bool
    action: str  # "BUY" | "SELL" | "NO_ACTION"
    conflicts: list[str]
    dominant_signal: str = ""
    dominant_tf: str = ""


def resolve_conflicts(
    signals_by_tf: dict[str, dict],
) -> ConflictResult:
    """Check for B/S conflicts across timeframes.

    Args:
        signals_by_tf: {timeframe: {"signal": "B2", "direction": "多"|"空", ...}}

    Rules:
        1. Same TF has both B and S → take the most recent one, flag conflict
        2. Large TF sell + small TF buy → NO_ACTION (rule 8.5 veto)
        3. All TFs agree on direction → pass through
        4. Any direction mismatch → NO_ACTION
    """
    buy_tfs: list[str] = []
    sell_tfs: list[str] = []
    conflicts: list[str] = []

    tf_order = ["1w", "1d", "1h", "30m", "15m", "5m"]

    for tf, info in signals_by_tf.items():
        sig = info.get("signal", "")
        if not sig:
            continue

        # Handle compound signals like "B2+S3"
        sig_parts = [s.strip() for s in sig.replace("+", ",").split(",") if s.strip()]
        has_buy = any(s in _BUY_TYPES for s in sig_parts)
        has_sell = any(s in _SELL_TYPES for s in sig_parts)

        if has_buy and has_sell:
            conflicts.append(f"{tf}: {sig} (同级别B+S矛盾)")
            continue  # drop this level entirely

        if has_buy:
            buy_tfs.append(tf)
        elif has_sell:
            sell_tfs.append(tf)

    if not buy_tfs and not sell_tfs:
        return ConflictResult(
            has_conflict=bool(conflicts),
            action="NO_ACTION",
            conflicts=conflicts,
        )

    # No cross-TF conflict
    if not buy_tfs or not sell_tfs:
        tfs = buy_tfs or sell_tfs
        action = "BUY" if buy_tfs else "SELL"
        # Use the largest TF as dominant
        dominant = _largest_tf(tfs, tf_order)
        return ConflictResult(
            has_conflict=bool(conflicts),
            action=action,
            conflicts=conflicts,
            dominant_signal=signals_by_tf.get(dominant, {}).get("signal", ""),
            dominant_tf=dominant,
        )

    # Cross-TF conflict: buy and sell on different TFs
    largest_buy = _largest_tf(buy_tfs, tf_order)
    largest_sell = _largest_tf(sell_tfs, tf_order)

    conflicts.append(
        f"跨级别冲突: {largest_buy}买 vs {largest_sell}卖"
    )

    # Rule 8.5: large TF always wins → but if conflicting, NO_ACTION
    return ConflictResult(
        has_conflict=True,
        action="NO_ACTION",
        conflicts=conflicts,
    )


def _largest_tf(tfs: list[str], tf_order: list[str]) -> str:
    """Return the largest (most significant) timeframe from the list."""
    for tf in tf_order:
        if tf in tfs:
            return tf
    return tfs[0] if tfs else ""
