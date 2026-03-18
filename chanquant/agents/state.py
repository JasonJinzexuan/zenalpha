"""LangGraph global state schema for the Agentic AI pipeline.

The SystemState is held by the Orchestrator and read/written by Workers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypedDict


class Phase(str, Enum):
    SCAN = "scan"
    NEST = "nest"
    SCORE = "score"
    ALERT = "alert"
    REPORT = "report"
    BACKTEST = "backtest"
    REVIEW = "review"


@dataclass(frozen=True)
class AgentScanResult:
    instrument: str
    signal_type: str
    level: str
    price: Decimal
    score: Decimal
    scan_time: datetime


@dataclass(frozen=True)
class AgentNesting:
    instrument: str
    target_level: str
    large_signal: str | None
    medium_signal: str | None
    precise_signal: str | None
    nesting_depth: int
    direction_aligned: bool
    confidence: Decimal


@dataclass(frozen=True)
class Alert:
    instrument: str
    signal_type: str
    channel: str  # slack / email / push / sms
    priority: str  # critical / high / medium / low
    message: str
    sent: bool = False


class SystemState(TypedDict, total=False):
    """LangGraph global state held by the Orchestrator."""

    instruments: list[str]
    scan_results: list[dict]
    nested_signals: list[dict]
    alerts_pending: list[dict]
    alerts_sent: list[dict]
    backtest_request: dict | None
    backtest_result: dict | None
    research_data: dict | None
    report: str | None
    current_phase: str
    errors: list[str]
    metadata: dict
    signal_outcomes: list[dict] | None
    calibration_params: dict | None
