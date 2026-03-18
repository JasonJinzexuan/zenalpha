"""Alerter Agent — notification routing based on signal priority.

Routes signals to appropriate channels based on a decision matrix.
Uses Haiku 4.5 for message formatting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from chanquant.agents.state import Alert, SystemState

# Decision matrix: signal_type → (channel, priority)
_DECISION_MATRIX: dict[str, tuple[str, str]] = {
    "B1": ("sms", "critical"),
    "S1": ("sms", "critical"),
    "B2": ("push", "high"),
    "S2": ("push", "high"),
    "B3": ("slack", "medium"),
    "S3": ("slack", "medium"),
}

# Dedup window in minutes
_DEDUP_WINDOW_MINUTES = 30


class AlerterAgent:
    """Route signals to notification channels based on decision matrix."""

    def __init__(self) -> None:
        self._sent_keys: dict[str, datetime] = {}

    def run(self, state: SystemState) -> SystemState:
        """Process nested signals and generate alerts."""
        nested = state.get("nested_signals", [])
        if not nested:
            state["current_phase"] = "report"
            return state

        alerts_pending: list[dict] = []
        alerts_sent = list(state.get("alerts_sent", []))

        for ns in nested:
            instrument = ns.get("instrument", "")
            signal_type = ns.get("large_signal") or ns.get("precise_signal", "")
            confidence = ns.get("confidence", "0")

            if not signal_type:
                continue

            # Dedup check
            dedup_key = f"{instrument}:{signal_type}"
            now = datetime.now()
            last_sent = self._sent_keys.get(dedup_key)
            if last_sent is not None:
                elapsed = (now - last_sent).total_seconds() / 60
                if elapsed < _DEDUP_WINDOW_MINUTES:
                    continue

            channel, priority = _DECISION_MATRIX.get(
                signal_type, ("email", "low")
            )

            # Nesting-confirmed signals get upgraded
            depth = ns.get("nesting_depth", 0)
            aligned = ns.get("direction_aligned", False)
            if depth >= 3 and aligned:
                if priority == "high":
                    priority = "critical"
                    channel = "sms"

            message = self._format_message(instrument, signal_type, ns)

            alert = {
                "instrument": instrument,
                "signal_type": signal_type,
                "channel": channel,
                "priority": priority,
                "message": message,
                "sent": False,
            }
            alerts_pending.append(alert)
            self._sent_keys[dedup_key] = now

        state["alerts_pending"] = alerts_pending
        state["current_phase"] = "report"
        return state

    def _format_message(
        self,
        instrument: str,
        signal_type: str,
        nesting: dict[str, Any],
    ) -> str:
        depth = nesting.get("nesting_depth", 0)
        aligned = nesting.get("direction_aligned", False)
        confidence = nesting.get("confidence", "0")
        target = nesting.get("target_level", "")

        parts = [
            f"[{signal_type}] {instrument}",
            f"Level: {target}" if target else "",
            f"Nesting: {depth} levels {'(aligned)' if aligned else '(misaligned)'}",
            f"Confidence: {confidence}",
        ]
        return " | ".join(p for p in parts if p)
