"""Report Agent — daily signal summary generation.

Produces Markdown reports summarizing all signals, nestings, and alerts.
Uses Sonnet 4.6 for narrative generation when available.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from chanquant.agents.bedrock import create_model
from chanquant.agents.state import SystemState


class ReportAgent:
    """Generate structured analysis reports from system state."""

    def __init__(self, use_llm: bool = True) -> None:
        self._use_llm = use_llm
        self._model = None
        if use_llm:
            try:
                self._model = create_model("report")
            except Exception:
                self._use_llm = False

    def run(self, state: SystemState) -> SystemState:
        """Generate a daily report and write it to state."""
        scan_results = state.get("scan_results", [])
        nested_signals = state.get("nested_signals", [])
        alerts_pending = state.get("alerts_pending", [])
        errors = state.get("errors", [])

        report = self._build_report(
            scan_results, nested_signals, alerts_pending, errors
        )
        state["report"] = report
        state["current_phase"] = "report"
        return state

    def _build_report(
        self,
        scan_results: list[dict],
        nested_signals: list[dict],
        alerts: list[dict],
        errors: list[str],
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Chan Theory Signal Report — {now}",
            "",
            "## Summary",
            f"- Signals detected: {len(scan_results)}",
            f"- Nesting confirmed: {len(nested_signals)}",
            f"- Alerts generated: {len(alerts)}",
            f"- Errors: {len(errors)}",
            "",
        ]

        if nested_signals:
            lines.append("## Top Signals (Nesting Confirmed)")
            lines.append("")
            lines.append("| Instrument | Signal | Level | Depth | Aligned | Confidence |")
            lines.append("|------------|--------|-------|-------|---------|------------|")
            for ns in sorted(
                nested_signals,
                key=lambda x: float(x.get("confidence", 0)),
                reverse=True,
            ):
                lines.append(
                    f"| {ns.get('instrument', '')} "
                    f"| {ns.get('large_signal', '')} "
                    f"| {ns.get('target_level', '')} "
                    f"| {ns.get('nesting_depth', 0)} "
                    f"| {'Yes' if ns.get('direction_aligned') else 'No'} "
                    f"| {ns.get('confidence', '0')} |"
                )
            lines.append("")

        if alerts:
            lines.append("## Alerts")
            lines.append("")
            for a in alerts:
                lines.append(
                    f"- **[{a.get('priority', '').upper()}]** "
                    f"{a.get('instrument', '')}: {a.get('message', '')}"
                )
            lines.append("")

        if scan_results:
            lines.append("## All Scan Results")
            lines.append("")
            # Group by instrument
            by_inst: dict[str, list[dict]] = {}
            for sr in scan_results:
                by_inst.setdefault(sr["instrument"], []).append(sr)

            for inst, sigs in sorted(by_inst.items()):
                sig_strs = [
                    f"{s['signal_type']}@{s['level']}" for s in sigs
                ]
                lines.append(f"- **{inst}**: {', '.join(sig_strs)}")
            lines.append("")

        if errors:
            lines.append("## Errors")
            lines.append("")
            for e in errors:
                lines.append(f"- `{e}`")
            lines.append("")

        return "\n".join(lines)
