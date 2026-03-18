"""Signal Reviewer Agent — weekly false-signal analysis (v2.1).

Analyzes INCORRECT signal outcomes to identify systematic patterns,
degradation trends, and calibration suggestions.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from chanquant.agents.bedrock import create_model
from chanquant.agents.prompts import load_prompt
from chanquant.core.objects import OutcomeType, SignalOutcome


class ReviewerAgent:
    """Analyze signal outcomes and produce weekly false-signal reports."""

    def __init__(self, use_llm: bool = True) -> None:
        self._use_llm = use_llm
        self._model = None
        self._prompt = ""
        if use_llm:
            try:
                self._model = create_model("signal-reviewer")
                self._prompt = load_prompt("reviewer_agent")
            except (FileNotFoundError, Exception):
                self._use_llm = False

    def review(
        self,
        outcomes: Sequence[SignalOutcome],
        period_label: str = "",
    ) -> dict[str, Any]:
        """Analyze outcomes and produce a review report.

        Args:
            outcomes: All evaluated SignalOutcome records for the period.
            period_label: Human-readable period label (e.g. "2026-W12").

        Returns:
            Review report dict with patterns, accuracy, and suggestions.
        """
        evaluated = [
            o for o in outcomes if o.outcome != OutcomeType.PENDING
        ]
        if not evaluated:
            return self._empty_report(period_label)

        # Basic statistics
        stats = self._compute_stats(evaluated)

        # Pattern detection (deterministic)
        patterns = self._detect_patterns(evaluated, stats)

        # Accuracy trend
        accuracy_trend = self._accuracy_trend(evaluated)

        # Calibration suggestions
        calibration = self._calibration_suggestions(stats, patterns)

        report = {
            "period": period_label or datetime.now().strftime("%Y-W%W"),
            "total_signals_evaluated": len(evaluated),
            "incorrect_count": stats["incorrect_count"],
            "overall_accuracy": str(stats["accuracy"]),
            "patterns_found": patterns,
            "accuracy_trend": accuracy_trend,
            "calibration_suggestions": calibration,
            "by_signal_type": stats["by_signal_type"],
            "by_regime": stats["by_regime"],
        }

        # Optionally enhance with LLM analysis
        if self._use_llm and self._model is not None:
            report["llm_analysis"] = self._llm_analysis(report, evaluated)

        return report

    def _compute_stats(
        self, outcomes: Sequence[SignalOutcome]
    ) -> dict[str, Any]:
        total = len(outcomes)
        correct = sum(1 for o in outcomes if o.outcome == OutcomeType.CORRECT)
        incorrect = sum(
            1 for o in outcomes if o.outcome == OutcomeType.INCORRECT
        )
        partial = sum(1 for o in outcomes if o.outcome == OutcomeType.PARTIAL)

        accuracy = Decimal(str(correct)) / Decimal(str(total)) if total else Decimal("0")

        # By signal type
        by_type: dict[str, dict[str, int]] = {}
        for o in outcomes:
            st = o.signal_type.value
            if st not in by_type:
                by_type[st] = {"total": 0, "correct": 0, "incorrect": 0}
            by_type[st]["total"] += 1
            if o.outcome == OutcomeType.CORRECT:
                by_type[st]["correct"] += 1
            elif o.outcome == OutcomeType.INCORRECT:
                by_type[st]["incorrect"] += 1

        # By market regime
        by_regime: dict[str, dict[str, int]] = {}
        for o in outcomes:
            regime = o.market_regime.name
            if regime not in by_regime:
                by_regime[regime] = {"total": 0, "correct": 0, "incorrect": 0}
            by_regime[regime]["total"] += 1
            if o.outcome == OutcomeType.CORRECT:
                by_regime[regime]["correct"] += 1
            elif o.outcome == OutcomeType.INCORRECT:
                by_regime[regime]["incorrect"] += 1

        return {
            "total": total,
            "correct": correct,
            "incorrect_count": incorrect,
            "partial": partial,
            "accuracy": accuracy,
            "by_signal_type": by_type,
            "by_regime": by_regime,
        }

    def _detect_patterns(
        self,
        outcomes: Sequence[SignalOutcome],
        stats: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify systematic false-signal patterns."""
        patterns: list[dict[str, Any]] = []
        incorrect = [o for o in outcomes if o.outcome == OutcomeType.INCORRECT]
        if not incorrect:
            return patterns

        overall_accuracy = float(stats["accuracy"])

        # Pattern 1: High VIX reduces accuracy
        high_vix = [o for o in outcomes if o.vix_at_signal and o.vix_at_signal > Decimal("35")]
        if len(high_vix) >= 5:
            hv_correct = sum(1 for o in high_vix if o.outcome == OutcomeType.CORRECT)
            hv_acc = hv_correct / len(high_vix) if high_vix else 0
            if hv_acc < overall_accuracy * 0.7:
                patterns.append({
                    "pattern_name": "high_vix_degradation",
                    "description": (
                        f"VIX > 35: accuracy {hv_acc:.0%} vs baseline {overall_accuracy:.0%}"
                    ),
                    "affected_signals": len(high_vix),
                    "suggested_action": "L9 filter: VIX > 35 → only weekly+ signals",
                    "confidence": 0.8,
                })

        # Pattern 2: Signal type with notably low accuracy
        for st, type_stats in stats["by_signal_type"].items():
            if type_stats["total"] >= 5:
                type_acc = type_stats["correct"] / type_stats["total"]
                if type_acc < overall_accuracy * 0.6:
                    patterns.append({
                        "pattern_name": f"low_accuracy_{st}",
                        "description": (
                            f"{st} accuracy {type_acc:.0%} vs baseline {overall_accuracy:.0%}"
                        ),
                        "affected_signals": type_stats["total"],
                        "suggested_action": f"Review {st} generation logic or increase threshold",
                        "confidence": 0.7,
                    })

        # Pattern 3: Regime-specific degradation
        for regime, regime_stats in stats["by_regime"].items():
            if regime_stats["total"] >= 5:
                r_acc = regime_stats["correct"] / regime_stats["total"]
                if r_acc < overall_accuracy * 0.6:
                    patterns.append({
                        "pattern_name": f"regime_{regime}_degradation",
                        "description": (
                            f"Regime {regime}: accuracy {r_acc:.0%} vs baseline {overall_accuracy:.0%}"
                        ),
                        "affected_signals": regime_stats["total"],
                        "suggested_action": f"Adjust timeframe weights for {regime} regime",
                        "confidence": 0.7,
                    })

        return patterns

    def _accuracy_trend(
        self, outcomes: Sequence[SignalOutcome]
    ) -> dict[str, Any]:
        """Compute accuracy trend over the evaluation period."""
        if not outcomes:
            return {"current_week": 0, "trend": "unknown"}

        # Sort by signal time
        sorted_outcomes = sorted(outcomes, key=lambda o: o.signal_time)
        total = len(sorted_outcomes)
        half = total // 2

        if half < 3:
            correct = sum(1 for o in outcomes if o.outcome == OutcomeType.CORRECT)
            acc = correct / total if total else 0
            return {"current_week": round(acc, 3), "trend": "insufficient_data"}

        first_half_correct = sum(
            1 for o in sorted_outcomes[:half] if o.outcome == OutcomeType.CORRECT
        )
        second_half_correct = sum(
            1 for o in sorted_outcomes[half:] if o.outcome == OutcomeType.CORRECT
        )

        first_acc = first_half_correct / half
        second_acc = second_half_correct / (total - half)

        if second_acc > first_acc + 0.05:
            trend = "improving"
        elif second_acc < first_acc - 0.05:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "current_week": round(second_acc, 3),
            "4_week_avg": round((first_acc + second_acc) / 2, 3),
            "trend": trend,
        }

    def _calibration_suggestions(
        self,
        stats: dict[str, Any],
        patterns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate parameter calibration suggestions based on patterns."""
        suggestions: list[dict[str, Any]] = []

        accuracy = float(stats["accuracy"])

        # If overall accuracy is low, suggest tightening divergence threshold
        if accuracy < 0.5 and stats["total"] >= 20:
            suggestions.append({
                "parameter": "divergence_strength_threshold",
                "current": 0.3,
                "suggested": 0.4,
                "reason": f"Overall accuracy {accuracy:.0%} below 50%, tighten filter",
            })

        # If specific patterns found, add targeted suggestions
        for p in patterns:
            if "high_vix" in p["pattern_name"]:
                suggestions.append({
                    "parameter": "vix_regime_filter",
                    "current": "none",
                    "suggested": "VIX>35 → weekly+ only",
                    "reason": p["description"],
                })

        return suggestions

    def _llm_analysis(
        self,
        report: dict[str, Any],
        outcomes: Sequence[SignalOutcome],
    ) -> str:
        """Use LLM to produce a narrative analysis of the review data."""
        if self._model is None:
            return ""

        # Prepare a summary for the LLM
        incorrect_summary = []
        for o in outcomes:
            if o.outcome == OutcomeType.INCORRECT:
                incorrect_summary.append({
                    "instrument": o.instrument,
                    "signal_type": o.signal_type.value,
                    "level": o.level.value,
                    "regime": o.market_regime.name,
                    "mae": str(o.max_adverse_excursion),
                    "mfe": str(o.max_favorable_excursion),
                })

        user_msg = (
            f"Review period: {report['period']}\n"
            f"Overall accuracy: {report['overall_accuracy']}\n"
            f"Incorrect signals ({report['incorrect_count']}):\n"
            f"{json.dumps(incorrect_summary[:20], indent=2)}\n\n"
            f"Patterns already detected:\n"
            f"{json.dumps(report['patterns_found'], indent=2)}\n\n"
            "Provide additional insights beyond the automated pattern detection. "
            "Focus on cross-dimensional patterns the code might have missed."
        )

        try:
            response = self._model.invoke([
                {"role": "system", "content": self._prompt},
                {"role": "user", "content": user_msg},
            ])
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            return f"LLM analysis unavailable: {exc}"

    def _empty_report(self, period_label: str) -> dict[str, Any]:
        return {
            "period": period_label or datetime.now().strftime("%Y-W%W"),
            "total_signals_evaluated": 0,
            "incorrect_count": 0,
            "overall_accuracy": "N/A",
            "patterns_found": [],
            "accuracy_trend": {"trend": "no_data"},
            "calibration_suggestions": [],
            "by_signal_type": {},
            "by_regime": {},
        }
