"""Nester Agent — multi-timeframe interval nesting (区间套).

Uses LLM reasoning (Sonnet 4.6) for cross-level signal positioning,
with a deterministic fallback when LLM is unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from chanquant.agents.bedrock import create_model
from chanquant.agents.prompts import load_prompt
from chanquant.agents.state import AgentNesting, SystemState
from chanquant.core.nesting import IntervalNester, merge_signals
from chanquant.core.objects import Signal, SignalType, TimeFrame


class NesterAgent:
    """Interval nesting agent with LLM reasoning + deterministic fallback."""

    def __init__(self, use_llm: bool = True) -> None:
        self._use_llm = use_llm
        self._nester = IntervalNester()
        self._model = None
        self._prompt = ""
        if use_llm:
            try:
                self._model = create_model("nester")
                self._prompt = load_prompt("nesting_agent")
            except (FileNotFoundError, Exception):
                self._use_llm = False

    def run(self, state: SystemState) -> SystemState:
        """Process scan results and produce nested signals.

        For each instrument with signals, either:
        - Use LLM to do multi-level reasoning, or
        - Use deterministic nesting (fallback)
        """
        scan_results = state.get("scan_results", [])
        if not scan_results:
            state["current_phase"] = "score"
            return state

        # Group signals by instrument
        by_instrument: dict[str, list[dict]] = {}
        for sr in scan_results:
            inst = sr["instrument"]
            by_instrument.setdefault(inst, []).append(sr)

        nested_signals: list[dict] = []
        errors = list(state.get("errors", []))

        for instrument, signals in by_instrument.items():
            try:
                if self._use_llm and self._model is not None:
                    result = self._llm_nesting(instrument, signals)
                else:
                    result = self._deterministic_nesting(instrument, signals)
                if result is not None:
                    nested_signals.append(result)
            except Exception as exc:
                errors.append(f"nester:{instrument}:{exc}")
                # Fallback to deterministic on LLM failure
                try:
                    result = self._deterministic_nesting(instrument, signals)
                    if result is not None:
                        nested_signals.append(result)
                except Exception:
                    pass

        state["nested_signals"] = nested_signals
        state["current_phase"] = "score"
        state["errors"] = errors
        return state

    def _deterministic_nesting(
        self, instrument: str, signals: list[dict]
    ) -> dict | None:
        """Fallback: deterministic nesting using code-only logic.

        Only confirms if large and medium timeframes agree on direction.
        Does NOT do sub-sub-level positioning (conservative).
        """
        # Group by level
        by_level: dict[str, list[dict]] = {}
        for s in signals:
            by_level.setdefault(s["level"], []).append(s)

        # Find largest level with signal
        level_order = ["1M", "1w", "1d", "30m", "5m", "1m"]
        large_sig = None
        medium_sig = None
        precise_sig = None

        found_levels: list[str] = []
        for lvl in level_order:
            if lvl in by_level:
                found_levels.append(lvl)

        if not found_levels:
            return None

        large_level = found_levels[0]
        large_sig = by_level[large_level][0]

        if len(found_levels) >= 2:
            medium_sig = by_level[found_levels[1]][0]
        if len(found_levels) >= 3:
            precise_sig = by_level[found_levels[2]][0]

        # Direction alignment check
        def is_buy(s: dict) -> bool:
            return s["signal_type"] in ("B1", "B2", "B3")

        aligned = True
        if medium_sig and is_buy(large_sig) != is_buy(medium_sig):
            aligned = False
        if precise_sig and is_buy(large_sig) != is_buy(precise_sig):
            aligned = False

        # Conflict: directions disagree → zero confidence
        if not aligned:
            smallest_sig = precise_sig or medium_sig or large_sig
            return {
                "instrument": instrument,
                "target_level": smallest_sig["level"],
                "large_signal": large_sig["signal_type"],
                "medium_signal": medium_sig["signal_type"] if medium_sig else None,
                "precise_signal": precise_sig["signal_type"] if precise_sig else None,
                "nesting_depth": len(found_levels),
                "direction_aligned": False,
                "confidence": "0",
                "confidence_source": "deterministic_fallback",
            }

        depth = len(found_levels)
        confidence = str(min(1.0, depth * 0.3 + (0.2 if aligned else 0)))

        return {
            "instrument": instrument,
            "target_level": found_levels[-1] if found_levels else large_level,
            "large_signal": large_sig["signal_type"],
            "medium_signal": medium_sig["signal_type"] if medium_sig else None,
            "precise_signal": precise_sig["signal_type"] if precise_sig else None,
            "nesting_depth": depth,
            "direction_aligned": aligned,
            "confidence": confidence,
            "confidence_source": "deterministic_fallback",
        }

    def _llm_nesting(
        self, instrument: str, signals: list[dict]
    ) -> dict | None:
        """Use LLM for multi-level interval nesting reasoning."""
        if self._model is None:
            return self._deterministic_nesting(instrument, signals)

        # Build input for LLM
        levels_summary: dict[str, Any] = {}
        for s in signals:
            lvl = s["level"]
            levels_summary[lvl] = {
                "signal_type": s["signal_type"],
                "strength": s.get("strength", "0"),
                "trend": s.get("trend"),
            }

        user_msg = (
            f"Instrument: {instrument}\n"
            f"Signals by level:\n{json.dumps(levels_summary, indent=2)}\n\n"
            "Perform interval nesting analysis. Follow the process in your system prompt."
        )

        try:
            response = self._model.invoke([
                {"role": "system", "content": self._prompt},
                {"role": "user", "content": user_msg},
            ])
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_llm_response(instrument, content, signals)
        except Exception:
            return self._deterministic_nesting(instrument, signals)

    def _parse_llm_response(
        self, instrument: str, response: str, signals: list[dict]
    ) -> dict | None:
        """Parse LLM JSON response, falling back to deterministic on parse failure."""
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                data["instrument"] = instrument
                data["confidence_source"] = "llm"
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return self._deterministic_nesting(instrument, signals)
