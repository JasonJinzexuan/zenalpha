"""Orchestrator Agent — Supervisor node for the Agentic AI pipeline.

Implements the Supervisor topology defined in PRD §3.2:
- Holds global SystemState
- Routes to Worker Agents in sequence: Scanner → Nester → Alerter → Report
- Handles errors and fallbacks
- Optionally integrates with LangGraph for stateful graph execution
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from chanquant.agents.state import Phase, SystemState
from chanquant.agents.scanner import ScannerAgent
from chanquant.agents.nester import NesterAgent
from chanquant.agents.alerter import AlerterAgent
from chanquant.agents.report import ReportAgent
from chanquant.agents.reviewer import ReviewerAgent
from chanquant.core.objects import RawKLine, SignalOutcome


class Orchestrator:
    """Central supervisor that routes work to specialized worker agents.

    The orchestration follows the pipeline:
        Scanner → Nester → Alerter → Report

    Signal Reviewer runs independently (weekly schedule).

    When LangGraph is available, this can be wrapped as a LangGraph
    Supervisor Node for checkpointing and async execution.
    """

    def __init__(self, use_llm: bool = False) -> None:
        self._scanner = ScannerAgent()
        self._nester = NesterAgent(use_llm=use_llm)
        self._alerter = AlerterAgent()
        self._report = ReportAgent(use_llm=use_llm)
        self._reviewer = ReviewerAgent(use_llm=use_llm)
        self._use_llm = use_llm

    def run_scan_cycle(
        self,
        instruments: list[str],
        klines_by_instrument: dict[str, Sequence[RawKLine]],
    ) -> SystemState:
        """Execute a full scan cycle: scan → nest → alert → report.

        Args:
            instruments: List of instrument symbols to scan.
            klines_by_instrument: K-line data for each instrument.

        Returns:
            Final SystemState with all results populated.
        """
        state: SystemState = {
            "instruments": instruments,
            "scan_results": [],
            "nested_signals": [],
            "alerts_pending": [],
            "alerts_sent": [],
            "backtest_request": None,
            "backtest_result": None,
            "research_data": None,
            "report": None,
            "current_phase": Phase.SCAN.value,
            "errors": [],
            "metadata": {
                "start_time": datetime.now().isoformat(),
                "instrument_count": len(instruments),
            },
            "signal_outcomes": None,
            "calibration_params": None,
        }

        # Phase 1: Scan (deterministic)
        state = self._run_phase(
            Phase.SCAN,
            lambda s: self._scanner.run(s, klines_by_instrument),
            state,
        )

        # Phase 2: Nest (LLM optional)
        state = self._run_phase(
            Phase.NEST,
            lambda s: self._nester.run(s),
            state,
        )

        # Phase 3: Alert
        state = self._run_phase(
            Phase.ALERT,
            lambda s: self._alerter.run(s),
            state,
        )

        # Phase 4: Report
        state = self._run_phase(
            Phase.REPORT,
            lambda s: self._report.run(s),
            state,
        )

        state["metadata"]["end_time"] = datetime.now().isoformat()
        return state

    def run_review(
        self,
        outcomes: Sequence[SignalOutcome],
        period_label: str = "",
    ) -> dict[str, Any]:
        """Run the Signal Reviewer Agent independently.

        Typically called on a weekly schedule (Saturday morning).

        Args:
            outcomes: All evaluated SignalOutcome records.
            period_label: E.g. "2026-W12".

        Returns:
            Review report dictionary.
        """
        return self._reviewer.review(outcomes, period_label)

    def _run_phase(
        self,
        phase: Phase,
        fn: Any,
        state: SystemState,
    ) -> SystemState:
        """Execute a phase with error handling."""
        state["current_phase"] = phase.value
        try:
            return fn(state)
        except Exception as exc:
            errors = list(state.get("errors", []))
            errors.append(f"orchestrator:{phase.value}:{exc}")
            state["errors"] = errors
            return state


def build_langgraph(use_llm: bool = False) -> Any:
    """Build a LangGraph StateGraph wrapping the Orchestrator.

    Returns a compiled LangGraph graph if langgraph is installed,
    or the raw Orchestrator otherwise.

    This function enables the agent pipeline to be run as a
    LangGraph graph with checkpointing, async execution, and
    visualization support.
    """
    orchestrator = Orchestrator(use_llm=use_llm)

    try:
        from langgraph.graph import StateGraph, END

        graph = StateGraph(SystemState)

        def scan_node(state: SystemState) -> SystemState:
            # Scanner needs klines, which are passed via metadata
            klines = state.get("metadata", {}).get("_klines", {})
            return orchestrator._scanner.run(state, klines)

        def nest_node(state: SystemState) -> SystemState:
            return orchestrator._nester.run(state)

        def alert_node(state: SystemState) -> SystemState:
            return orchestrator._alerter.run(state)

        def report_node(state: SystemState) -> SystemState:
            return orchestrator._report.run(state)

        def should_nest(state: SystemState) -> str:
            """Route: if scan found signals → nest, else → report."""
            if state.get("scan_results"):
                return "nest"
            return "report"

        def should_alert(state: SystemState) -> str:
            """Route: if nesting confirmed signals → alert, else → report."""
            if state.get("nested_signals"):
                return "alert"
            return "report"

        graph.add_node("scan", scan_node)
        graph.add_node("nest", nest_node)
        graph.add_node("alert", alert_node)
        graph.add_node("report", report_node)

        graph.set_entry_point("scan")
        graph.add_conditional_edges("scan", should_nest, {"nest": "nest", "report": "report"})
        graph.add_conditional_edges("nest", should_alert, {"alert": "alert", "report": "report"})
        graph.add_edge("alert", "report")
        graph.add_edge("report", END)

        return graph.compile()

    except ImportError:
        return orchestrator
