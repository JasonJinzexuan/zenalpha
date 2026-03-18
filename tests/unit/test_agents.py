"""Tests for the Agentic AI framework.

Tests run WITHOUT LLM/Bedrock — all agents fall back to deterministic mode.
"""

from datetime import datetime
from decimal import Decimal

from chanquant.agents.bedrock import AGENT_MODEL_MAP, ModelTier, create_model
from chanquant.agents.prompts import list_versions, load_prompt, get_prompt_dir
from chanquant.agents.scanner import ScannerAgent
from chanquant.agents.nester import NesterAgent
from chanquant.agents.alerter import AlerterAgent
from chanquant.agents.report import ReportAgent
from chanquant.agents.reviewer import ReviewerAgent
from chanquant.agents.orchestrator import Orchestrator
from chanquant.agents.state import Phase, SystemState
from chanquant.core.objects import (
    MarketRegime,
    OutcomeType,
    RawKLine,
    SignalOutcome,
    SignalType,
    TimeFrame,
)


def _bar(ts: datetime, close: str = "100") -> RawKLine:
    return RawKLine(
        timestamp=ts,
        open=Decimal(close),
        high=Decimal(close) + Decimal("2"),
        low=Decimal(close) - Decimal("2"),
        close=Decimal(close),
        volume=10000,
    )


# ── Bedrock Model Factory ───────────────────────────────────────────────────


class TestBedrock:
    def test_agent_model_map_has_all_agents(self):
        expected = {
            "orchestrator", "scanner", "nester", "research",
            "backtester", "alerter", "report", "signal-reviewer",
            "segment-agent", "structure-agent", "divergence-agent",
            "signal-agent", "nesting-agent",
        }
        assert expected == set(AGENT_MODEL_MAP.keys())

    def test_create_model_returns_stub_without_langchain(self):
        model = create_model("scanner")
        # Should be a StubModel since langchain-aws is not installed
        assert "StubModel" in repr(model) or hasattr(model, "invoke")

    def test_orchestrator_uses_opus(self):
        config = AGENT_MODEL_MAP["orchestrator"]
        assert config.tier == ModelTier.OPUS

    def test_nester_uses_sonnet(self):
        config = AGENT_MODEL_MAP["nester"]
        assert config.tier == ModelTier.SONNET

    def test_unknown_agent_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown agent"):
            create_model("nonexistent")


# ── Prompt Version Management ────────────────────────────────────────────────


class TestPrompts:
    def test_prompt_dir_exists(self):
        assert get_prompt_dir().is_dir()

    def test_list_versions_segment_agent(self):
        versions = list_versions("segment_agent")
        assert len(versions) >= 1
        assert versions[0].version == "v1.0.0"

    def test_load_prompt_divergence_agent(self):
        content = load_prompt("divergence_agent")
        assert "Divergence Agent" in content
        assert "a vs c" in content or "a_macd_area" in content

    def test_load_prompt_reviewer(self):
        content = load_prompt("reviewer_agent")
        assert "Signal Reviewer" in content

    def test_load_nonexistent_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_agent")

    def test_all_agents_have_prompts(self):
        agents = [
            "segment_agent", "structure_agent", "divergence_agent",
            "signal_agent", "nesting_agent", "reviewer_agent",
        ]
        for agent in agents:
            versions = list_versions(agent)
            assert len(versions) >= 1, f"No prompts for {agent}"


# ── Scanner Agent ────────────────────────────────────────────────────────────


class TestScannerAgent:
    def test_empty_input_no_results(self):
        scanner = ScannerAgent()
        state: SystemState = {
            "instruments": [],
            "scan_results": [],
            "errors": [],
            "current_phase": "scan",
            "metadata": {},
        }
        result = scanner.run(state, {})
        assert result["scan_results"] == []
        assert result["current_phase"] == "nest"

    def test_processes_klines_without_error(self):
        scanner = ScannerAgent()
        state: SystemState = {
            "instruments": ["TEST"],
            "scan_results": [],
            "errors": [],
            "current_phase": "scan",
            "metadata": {},
        }
        bars = [_bar(datetime(2026, 1, 1, i)) for i in range(10)]
        result = scanner.run(state, {"TEST": bars})
        assert "errors" in result
        assert result["current_phase"] == "nest"


# ── Nester Agent ─────────────────────────────────────────────────────────────


class TestNesterAgent:
    def test_deterministic_fallback(self):
        nester = NesterAgent(use_llm=False)
        state: SystemState = {
            "scan_results": [
                {"instrument": "AAPL", "signal_type": "B1", "level": "1d", "strength": "0.8", "trend": "DOWN_TREND", "price": "150", "timestamp": "2026-03-18T10:00:00"},
                {"instrument": "AAPL", "signal_type": "B2", "level": "30m", "strength": "0.6", "trend": "DOWN_TREND", "price": "148", "timestamp": "2026-03-18T10:00:00"},
            ],
            "nested_signals": [],
            "errors": [],
            "current_phase": "nest",
            "metadata": {},
        }
        result = nester.run(state)
        assert len(result["nested_signals"]) == 1
        ns = result["nested_signals"][0]
        assert ns["instrument"] == "AAPL"
        assert ns["nesting_depth"] == 2
        assert ns["confidence_source"] == "deterministic_fallback"

    def test_empty_scan_results(self):
        nester = NesterAgent(use_llm=False)
        state: SystemState = {
            "scan_results": [],
            "nested_signals": [],
            "errors": [],
            "current_phase": "nest",
            "metadata": {},
        }
        result = nester.run(state)
        assert result["nested_signals"] == []

    def test_conflict_zeroes_confidence(self):
        nester = NesterAgent(use_llm=False)
        state: SystemState = {
            "scan_results": [
                {"instrument": "AAPL", "signal_type": "S1", "level": "1d", "strength": "0.8", "trend": "UP_TREND", "price": "150", "timestamp": "2026-03-18T10:00:00"},
                {"instrument": "AAPL", "signal_type": "B1", "level": "5m", "strength": "0.7", "trend": "DOWN_TREND", "price": "148", "timestamp": "2026-03-18T10:00:00"},
            ],
            "nested_signals": [],
            "errors": [],
            "current_phase": "nest",
            "metadata": {},
        }
        result = nester.run(state)
        ns = result["nested_signals"][0]
        assert ns["confidence"] == "0"
        assert ns["direction_aligned"] is False


# ── Alerter Agent ────────────────────────────────────────────────────────────


class TestAlerterAgent:
    def test_routes_b1_to_sms(self):
        alerter = AlerterAgent()
        state: SystemState = {
            "nested_signals": [
                {"instrument": "AAPL", "large_signal": "B1", "target_level": "1d",
                 "nesting_depth": 2, "direction_aligned": True, "confidence": "0.8"},
            ],
            "alerts_pending": [],
            "alerts_sent": [],
            "errors": [],
            "current_phase": "alert",
            "metadata": {},
        }
        result = alerter.run(state)
        assert len(result["alerts_pending"]) == 1
        alert = result["alerts_pending"][0]
        assert alert["channel"] == "sms"
        assert alert["priority"] == "critical"

    def test_routes_b3_to_slack(self):
        alerter = AlerterAgent()
        state: SystemState = {
            "nested_signals": [
                {"instrument": "TSLA", "large_signal": "B3", "target_level": "30m",
                 "nesting_depth": 1, "direction_aligned": True, "confidence": "0.5"},
            ],
            "alerts_pending": [],
            "alerts_sent": [],
            "errors": [],
            "current_phase": "alert",
            "metadata": {},
        }
        result = alerter.run(state)
        alert = result["alerts_pending"][0]
        assert alert["channel"] == "slack"
        assert alert["priority"] == "medium"

    def test_dedup_within_30_min(self):
        alerter = AlerterAgent()
        nested = [
            {"instrument": "AAPL", "large_signal": "B1", "target_level": "1d",
             "nesting_depth": 2, "direction_aligned": True, "confidence": "0.8"},
        ]
        state: SystemState = {
            "nested_signals": nested,
            "alerts_pending": [],
            "alerts_sent": [],
            "errors": [],
            "current_phase": "alert",
            "metadata": {},
        }
        # First run generates alert
        result1 = alerter.run(state)
        assert len(result1["alerts_pending"]) == 1
        # Second run dedups
        state["alerts_pending"] = []
        result2 = alerter.run(state)
        assert len(result2["alerts_pending"]) == 0


# ── Report Agent ─────────────────────────────────────────────────────────────


class TestReportAgent:
    def test_generates_markdown_report(self):
        report_agent = ReportAgent(use_llm=False)
        state: SystemState = {
            "scan_results": [
                {"instrument": "AAPL", "signal_type": "B1", "level": "1d"},
            ],
            "nested_signals": [
                {"instrument": "AAPL", "large_signal": "B1", "target_level": "1d",
                 "nesting_depth": 2, "direction_aligned": True, "confidence": "0.8"},
            ],
            "alerts_pending": [],
            "errors": [],
            "current_phase": "report",
            "metadata": {},
        }
        result = report_agent.run(state)
        assert result["report"] is not None
        assert "# Chan Theory Signal Report" in result["report"]
        assert "AAPL" in result["report"]


# ── Reviewer Agent ───────────────────────────────────────────────────────────


class TestReviewerAgent:
    def _outcomes(self, n_correct: int, n_incorrect: int) -> list[SignalOutcome]:
        outcomes = []
        for i in range(n_correct):
            outcomes.append(SignalOutcome(
                signal_id=f"c{i}",
                instrument="AAPL",
                signal_type=SignalType.B1,
                level=TimeFrame.DAILY,
                signal_price=Decimal("150"),
                signal_time=datetime(2026, 3, 10 + i),
                outcome=OutcomeType.CORRECT,
                market_regime=MarketRegime.NORMAL,
            ))
        for i in range(n_incorrect):
            outcomes.append(SignalOutcome(
                signal_id=f"i{i}",
                instrument="TSLA",
                signal_type=SignalType.B1,
                level=TimeFrame.DAILY,
                signal_price=Decimal("200"),
                signal_time=datetime(2026, 3, 10 + i),
                outcome=OutcomeType.INCORRECT,
                max_adverse_excursion=Decimal("20"),
                market_regime=MarketRegime.HIGH_VOL,
            ))
        return outcomes

    def test_empty_outcomes(self):
        reviewer = ReviewerAgent(use_llm=False)
        report = reviewer.review([], "2026-W12")
        assert report["total_signals_evaluated"] == 0

    def test_basic_review(self):
        reviewer = ReviewerAgent(use_llm=False)
        outcomes = self._outcomes(7, 3)
        report = reviewer.review(outcomes, "2026-W12")
        assert report["total_signals_evaluated"] == 10
        assert report["incorrect_count"] == 3
        assert float(report["overall_accuracy"]) == 0.7

    def test_detects_regime_pattern(self):
        reviewer = ReviewerAgent(use_llm=False)
        # All incorrect signals are HIGH_VOL, all correct are NORMAL
        outcomes = self._outcomes(10, 8)
        report = reviewer.review(outcomes, "2026-W12")
        # Should detect HIGH_VOL degradation
        regime_patterns = [
            p for p in report["patterns_found"]
            if "regime" in p["pattern_name"]
        ]
        # HIGH_VOL has 0 correct / 8 total → 0% vs 55% baseline → pattern detected
        assert len(regime_patterns) >= 1

    def test_accuracy_trend(self):
        reviewer = ReviewerAgent(use_llm=False)
        outcomes = self._outcomes(15, 5)
        report = reviewer.review(outcomes, "2026-W12")
        assert "trend" in report["accuracy_trend"]


# ── Orchestrator (Full Pipeline) ─────────────────────────────────────────────


class TestOrchestrator:
    def test_full_cycle_no_data(self):
        orch = Orchestrator(use_llm=False)
        state = orch.run_scan_cycle([], {})
        assert state["current_phase"] == "report"
        assert state["report"] is not None

    def test_full_cycle_with_data(self):
        orch = Orchestrator(use_llm=False)
        bars = [_bar(datetime(2026, 1, 1, i)) for i in range(10)]
        state = orch.run_scan_cycle(["TEST"], {"TEST": bars})
        assert "start_time" in state["metadata"]
        assert "end_time" in state["metadata"]
        assert state["report"] is not None

    def test_review_independent(self):
        orch = Orchestrator(use_llm=False)
        outcomes = [
            SignalOutcome(
                signal_id="x1",
                instrument="AAPL",
                signal_type=SignalType.B1,
                level=TimeFrame.DAILY,
                signal_price=Decimal("150"),
                signal_time=datetime(2026, 3, 15),
                outcome=OutcomeType.CORRECT,
            ),
        ]
        report = orch.run_review(outcomes, "2026-W12")
        assert report["total_signals_evaluated"] == 1
