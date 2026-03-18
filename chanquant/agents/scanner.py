"""Scanner Agent — deterministic code, no LLM (v2.2).

Runs the full L0-L7 pipeline on all instruments in the pool.
Outputs initial signals for Nester Agent to refine.
"""

from __future__ import annotations

from typing import Any, Sequence

from chanquant.agents.state import AgentScanResult, SystemState
from chanquant.agents.tools import analyze_instrument
from chanquant.core.objects import RawKLine


class ScannerAgent:
    """Pure deterministic scanner — no LLM calls.

    Processes all instruments through the analysis pipeline and
    writes raw scan results into the system state.
    """

    def run(
        self,
        state: SystemState,
        klines_by_instrument: dict[str, Sequence[RawKLine]],
    ) -> SystemState:
        """Execute scanning phase.

        Args:
            state: Current system state.
            klines_by_instrument: K-line data keyed by instrument symbol.

        Returns:
            Updated state with scan_results populated.
        """
        scan_results: list[dict] = []
        errors: list[str] = list(state.get("errors", []))

        for instrument, klines in klines_by_instrument.items():
            try:
                result = analyze_instrument(klines, instrument)
                if result.get("signals"):
                    for sig in result["signals"]:
                        scan_results.append({
                            "instrument": instrument,
                            "signal_type": sig["signal_type"],
                            "level": sig["level"],
                            "price": sig["price"],
                            "strength": sig["strength"],
                            "timestamp": sig["timestamp"],
                            "trend": result.get("trend"),
                        })
            except Exception as exc:
                errors.append(f"scanner:{instrument}:{exc}")

        state["scan_results"] = scan_results
        state["current_phase"] = "nest"
        state["errors"] = errors
        return state
