"""LangGraph-based LLM pipeline for Chan Theory analysis.

Replaces the deterministic L3-L7 layers with LLM agents:
- L0-L2: Deterministic (K-line merge, fractal, stroke) — runs first
- L3: Segment Agent (Haiku) — judges segment termination
- L4-L5: Structure Agent (Haiku) — classifies centers + trend
- L6: Divergence Agent (Sonnet) — determines divergence
- L7: Signal Agent (Sonnet) — generates buy/sell signals
- L8: Nesting Agent (Sonnet) — multi-timeframe interval nesting
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any, Sequence, TypedDict

from chanquant.agents.bedrock import create_model
from chanquant.agents.prompts import load_prompt
from chanquant.core.kline import KLineProcessor
from chanquant.core.fractal import FractalDetector
from chanquant.core.macd import IncrementalMACD
from chanquant.core.objects import (
    Fractal,
    MACDValue,
    RawKLine,
    StandardKLine,
    Stroke,
    TimeFrame,
)
from chanquant.core.stroke import StrokeBuilder, attach_macd_area


# ── LangGraph State ──────────────────────────────────────────────────────────


class LLMPipelineState(TypedDict, total=False):
    """State flowing through the LangGraph LLM pipeline."""

    instrument: str
    level: str

    # L0-L2 deterministic outputs
    standard_klines: list[dict]
    fractals: list[dict]
    strokes: list[dict]
    macd_values: list[dict]

    # L3: Segment Agent output
    segments: list[dict]

    # L4-L5: Structure Agent output
    centers: list[dict]
    trend: dict | None

    # L6: Divergence Agent output
    divergence: dict | None

    # L7: Signal Agent output
    signals: list[dict]

    # L8: Nesting Agent output
    nesting: dict | None

    errors: list[str]


# ── Serializers ──────────────────────────────────────────────────────────────


def _fractal_to_dict(f: Fractal) -> dict:
    return {
        "type": f.type.name,
        "timestamp": f.timestamp.isoformat(),
        "price": str(f.extreme_value),
        "kline_index": f.kline_index,
    }


def _stroke_to_dict(s: Stroke) -> dict:
    return {
        "direction": s.direction.name,
        "start_index": s.start_fractal.kline_index,
        "end_index": s.end_fractal.kline_index,
        "start_price": str(s.start_fractal.extreme_value),
        "end_price": str(s.end_fractal.extreme_value),
        "start_time": s.start_fractal.timestamp.isoformat(),
        "end_time": s.end_fractal.timestamp.isoformat(),
        "kline_count": s.kline_count,
        "macd_area": str(s.macd_area),
        "high": str(s.high),
        "low": str(s.low),
    }


def _kline_to_dict(k: StandardKLine) -> dict:
    return {
        "timestamp": k.timestamp.isoformat(),
        "open": str(k.open),
        "high": str(k.high),
        "low": str(k.low),
        "close": str(k.close),
        "volume": k.volume,
    }


def _macd_to_dict(m: MACDValue) -> dict:
    return {"dif": str(m.dif), "dea": str(m.dea), "histogram": str(m.histogram)}


# ── L0-L2 Deterministic Node ────────────────────────────────────────────────


def run_deterministic_l0_l2(klines: Sequence[RawKLine]) -> LLMPipelineState:
    """Run L0 (K-line merge + MACD), L1 (fractal), L2 (stroke) deterministically.

    Returns the initial state for the LangGraph pipeline.
    """
    kline_proc = KLineProcessor()
    macd = IncrementalMACD()
    fractal_det = FractalDetector()
    stroke_builder = StrokeBuilder()

    std_klines: list[StandardKLine] = []
    macd_values: list[MACDValue] = []
    fractals: list[Fractal] = []
    strokes: list[Stroke] = []

    for raw in klines:
        macd_val = macd.feed(raw.close)
        macd_values.append(macd_val)

        std = kline_proc.feed(raw)
        if std is None:
            continue
        std_klines.append(std)

        fractal = fractal_det.feed(std)
        if fractal is None:
            continue
        fractals.append(fractal)

        stroke = stroke_builder.feed(fractal)
        if stroke is None:
            continue

        start_idx = stroke.start_fractal.kline_index
        end_idx = stroke.end_fractal.kline_index
        stroke = attach_macd_area(stroke, macd_values, start_idx, end_idx)
        strokes.append(stroke)

    return {
        "standard_klines": [_kline_to_dict(k) for k in std_klines],
        "fractals": [_fractal_to_dict(f) for f in fractals],
        "strokes": [_stroke_to_dict(s) for s in strokes],
        "macd_values": [_macd_to_dict(m) for m in macd_values[-50:]],  # last 50 for context
        "segments": [],
        "centers": [],
        "trend": None,
        "divergence": None,
        "signals": [],
        "nesting": None,
        "errors": [],
    }


# ── LLM Helper ──────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks and trailing commas."""
    import re

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)

    # Find outermost { ... }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None

    candidate = text[start:end]

    # Try direct parse first
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fix trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Fix single quotes → double quotes (common LLM mistake)
    fixed2 = candidate.replace("'", '"')
    fixed2 = re.sub(r",\s*([}\]])", r"\1", fixed2)
    try:
        return json.loads(fixed2)
    except json.JSONDecodeError:
        return None


_JSON_SUFFIX = (
    "\n\nIMPORTANT: Respond with ONLY a single JSON object. "
    "No markdown, no explanation, no text before or after the JSON. "
    "Start your response with { and end with }."
)


def _invoke_llm(agent_name: str, prompt_name: str, user_message: str) -> dict | None:
    """Invoke an LLM agent and parse JSON response."""
    model = create_model(agent_name)
    system_prompt = load_prompt(prompt_name) + _JSON_SUFFIX

    response = model.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ])
    content = response.content if hasattr(response, "content") else str(response)
    return _extract_json(content)


# ── L3: Segment Agent Node ──────────────────────────────────────────────────


def segment_node(state: LLMPipelineState) -> LLMPipelineState:
    """L3: Use LLM to build segments from strokes."""
    strokes = state.get("strokes", [])
    errors = list(state.get("errors", []))

    if len(strokes) < 3:
        return {**state, "segments": [], "errors": errors}

    user_msg = json.dumps({
        "strokes": strokes,
        "instruction": (
            "Analyze these strokes and identify all segments (线段). "
            "A segment needs at least 3 strokes. Determine termination type "
            "(FIRST_KIND or SECOND_KIND) for each segment. "
            "Return JSON: {\"segments\": [{\"direction\": \"UP/DOWN\", "
            "\"stroke_indices\": [start, end], \"high\": float, \"low\": float, "
            "\"termination_type\": \"FIRST_KIND/SECOND_KIND\", "
            "\"start_time\": str, \"end_time\": str, \"reasoning\": str}]}"
        ),
    }, indent=2)

    try:
        result = _invoke_llm("segment-agent", "segment_agent", user_msg)
        segments = result.get("segments", []) if result else []
        return {**state, "segments": segments, "errors": errors}
    except Exception as exc:
        errors.append(f"segment_agent:{exc}")
        return {**state, "segments": [], "errors": errors}


# ── L4-L5: Structure Agent Node ─────────────────────────────────────────────


def structure_node(state: LLMPipelineState) -> LLMPipelineState:
    """L4-L5: Use LLM to detect centers and classify trend structure."""
    segments = state.get("segments", [])
    errors = list(state.get("errors", []))

    if not segments:
        return {**state, "centers": [], "trend": None, "errors": errors}

    user_msg = json.dumps({
        "segments": segments,
        "macd_values": state.get("macd_values", [])[-30:],
        "instruction": (
            "Analyze these segments to: "
            "1) Detect centers (中枢) — overlapping segment ranges. "
            "2) Classify trend: UP_TREND (2+ ascending non-overlapping centers), "
            "DOWN_TREND (2+ descending), or CONSOLIDATION (1 center). "
            "3) Identify a+A+b+B+c structure if trend exists. "
            "Return JSON: {\"centers\": [{\"zg\": float, \"zd\": float, "
            "\"gg\": float, \"dd\": float, \"start_time\": str, \"end_time\": str, "
            "\"extension_count\": int}], \"trend\": {\"classification\": "
            "\"UP_TREND/DOWN_TREND/CONSOLIDATION\", \"segment_a\": {...}, "
            "\"center_A\": {...}, \"segment_b\": {...}, \"center_B\": {...}, "
            "\"segment_c\": {...}, \"completion_status\": "
            "\"EXTENDING/COMPLETING/COMPLETED\"}, \"reasoning\": str, "
            "\"confidence\": float}"
        ),
    }, indent=2)

    try:
        result = _invoke_llm("structure-agent", "structure_agent", user_msg)
        if result:
            centers = result.get("centers", [])
            trend = result.get("trend")
            return {**state, "centers": centers, "trend": trend, "errors": errors}
        return {**state, "centers": [], "trend": None, "errors": errors}
    except Exception as exc:
        errors.append(f"structure_agent:{exc}")
        return {**state, "centers": [], "trend": None, "errors": errors}


# ── L6: Divergence Agent Node ───────────────────────────────────────────────


def divergence_node(state: LLMPipelineState) -> LLMPipelineState:
    """L6: Use LLM to detect divergence between segments a and c."""
    trend = state.get("trend")
    errors = list(state.get("errors", []))

    if not trend:
        return {**state, "divergence": None, "errors": errors}

    classification = trend.get("classification", "")
    if classification == "CONSOLIDATION":
        return {**state, "divergence": None, "errors": errors}

    user_msg = json.dumps({
        "trend": trend,
        "segments": state.get("segments", []),
        "macd_values": state.get("macd_values", []),
        "instruction": (
            "Determine if MACD divergence (背驰) exists. "
            "Compare segment_a vs segment_c MACD areas. "
            "Check: 1) MACD returns near zero at center B, "
            "2) At least 2 of 3 confirmations (area, DIF peak, stagnation), "
            "3) Volume if available. "
            "Return JSON per the divergence agent output format."
        ),
    }, indent=2)

    try:
        result = _invoke_llm("divergence-agent", "divergence_agent", user_msg)
        divergence = result if result and result.get("has_divergence") else None
        return {**state, "divergence": divergence, "errors": errors}
    except Exception as exc:
        errors.append(f"divergence_agent:{exc}")
        return {**state, "divergence": None, "errors": errors}


# ── L7: Signal Agent Node ───────────────────────────────────────────────────


def signal_node(state: LLMPipelineState) -> LLMPipelineState:
    """L7: Use LLM to generate buy/sell signals."""
    errors = list(state.get("errors", []))
    trend = state.get("trend")
    centers = state.get("centers", [])

    if not trend and not centers:
        return {**state, "signals": [], "errors": errors}

    user_msg = json.dumps({
        "instrument": state.get("instrument", ""),
        "trend": trend,
        "divergence": state.get("divergence"),
        "centers": centers,
        "segments": state.get("segments", []),
        "strokes": state.get("strokes", [])[-10:],  # last 10 for context
        "instruction": (
            "Generate buy/sell signals (B1-B3, S1-S3) based on the analysis. "
            "B1/S1: trend divergence reversal. "
            "B2/S2: no new extreme after B1/S1, consolidation divergence, or small-to-large. "
            "B3/S3: center break + first pullback. "
            "Return JSON per the signal agent output format."
        ),
    }, indent=2)

    try:
        result = _invoke_llm("signal-agent", "signal_agent", user_msg)
        signals = result.get("signals", []) if result else []
        # Enrich with instrument
        for sig in signals:
            sig["instrument"] = state.get("instrument", "")
            sig["level"] = state.get("level", "1d")
        return {**state, "signals": signals, "errors": errors}
    except Exception as exc:
        errors.append(f"signal_agent:{exc}")
        return {**state, "signals": [], "errors": errors}


# ── L8: Nesting Agent Node (with tool use) ──────────────────────────────────


def nesting_node(state: LLMPipelineState) -> LLMPipelineState:
    """L8: Multi-timeframe interval nesting with tool use.

    The agent autonomously fetches data for multiple timeframes
    via tools (run_pipeline, compare_divergence, get_market_summary)
    and synthesizes a nesting analysis.
    """
    instrument = state.get("instrument", "")
    errors = list(state.get("errors", []))

    if not instrument:
        return {**state, "nesting": None, "errors": errors}

    try:
        from chanquant.agents.nester import NesterAgent

        nester = NesterAgent(use_llm=True)
        result = nester.analyze_instrument(instrument)
        return {**state, "nesting": result, "errors": errors}
    except Exception as exc:
        errors.append(f"nesting_agent:{exc}")
        return {**state, "nesting": None, "errors": errors}


# ── Conditional Routing ──────────────────────────────────────────────────────


def should_run_structure(state: LLMPipelineState) -> str:
    """Route: segments found → structure, else → end."""
    if state.get("segments"):
        return "structure"
    return "signal"  # skip to signal (may still have B3 from centers)


def should_run_divergence(state: LLMPipelineState) -> str:
    """Route: trend exists (not consolidation) → divergence, else → signal."""
    trend = state.get("trend")
    if trend and trend.get("classification") in ("UP_TREND", "DOWN_TREND"):
        return "divergence"
    return "signal"


def should_run_nesting(state: LLMPipelineState) -> str:
    """Route: signals found → nesting, else → end."""
    if state.get("signals"):
        return "nesting"
    return "end"


# ── Build LangGraph ─────────────────────────────────────────────────────────


def build_llm_pipeline() -> Any:
    """Build the LangGraph-based LLM analysis pipeline.

    Graph: segment → structure → divergence → signal → nesting

    Returns a compiled LangGraph graph.
    Raises ImportError if langgraph is not installed.
    """
    from langgraph.graph import StateGraph, END

    graph = StateGraph(LLMPipelineState)

    graph.add_node("segment", segment_node)
    graph.add_node("structure", structure_node)
    graph.add_node("divergence", divergence_node)
    graph.add_node("signal", signal_node)
    graph.add_node("nesting", nesting_node)

    graph.set_entry_point("segment")
    graph.add_conditional_edges("segment", should_run_structure, {
        "structure": "structure",
        "signal": "signal",
    })
    graph.add_conditional_edges("structure", should_run_divergence, {
        "divergence": "divergence",
        "signal": "signal",
    })
    graph.add_edge("divergence", "signal")
    graph.add_conditional_edges("signal", should_run_nesting, {
        "nesting": "nesting",
        "end": END,
    })
    graph.add_edge("nesting", END)

    return graph.compile()


def run_llm_analysis(
    klines: Sequence[RawKLine],
    instrument: str = "",
    level: str = "1d",
) -> LLMPipelineState:
    """Run the full LLM-based analysis pipeline.

    1. Deterministic L0-L2
    2. LangGraph L3-L8 (LLM agents)
    """
    # Phase 1: Deterministic
    state = run_deterministic_l0_l2(klines)
    state["instrument"] = instrument
    state["level"] = level

    # Phase 2: LangGraph LLM pipeline
    graph = build_llm_pipeline()
    result = graph.invoke(state)
    return result


# ── Stage-tracked execution ────────────────────────────────────────────────


class StageResult(TypedDict):
    """Result from a single pipeline stage."""

    name: str
    status: str  # "success" | "skipped" | "error"
    duration_ms: int
    input_summary: dict
    output_summary: dict
    error: str | None


def _summarize_state_diff(before: dict, after: dict) -> dict:
    """Extract what changed between two pipeline states."""
    diff: dict[str, Any] = {}
    for key in ("segments", "centers", "trend", "divergence", "signals", "nesting"):
        bval = before.get(key)
        aval = after.get(key)
        if bval != aval:
            diff[key] = aval
    return diff


def _input_summary_for(node_name: str, state: dict) -> dict:
    """Build a concise input summary for a given node."""
    if node_name == "segment":
        strokes = state.get("strokes", [])
        return {"stroke_count": len(strokes), "strokes_preview": strokes[:3]}
    if node_name == "structure":
        return {"segment_count": len(state.get("segments", []))}
    if node_name == "divergence":
        return {"trend": state.get("trend"), "segment_count": len(state.get("segments", []))}
    if node_name == "signal":
        return {
            "trend": state.get("trend"),
            "divergence": state.get("divergence"),
            "center_count": len(state.get("centers", [])),
        }
    if node_name == "nesting":
        return {"signal_count": len(state.get("signals", []))}
    return {}


_NODE_ORDER = ["segment", "structure", "divergence", "signal", "nesting"]


def run_llm_analysis_with_stages(
    klines: Sequence[RawKLine],
    instrument: str = "",
    level: str = "1d",
) -> dict:
    """Run the LLM pipeline and capture per-stage input/output/timing.

    Returns dict with keys: "result" (final state) and "stages" (list of StageResult).
    """
    # Phase 1: Deterministic
    t0 = time.monotonic()
    state = run_deterministic_l0_l2(klines)
    state["instrument"] = instrument
    state["level"] = level
    det_ms = int((time.monotonic() - t0) * 1000)

    stages: list[StageResult] = [
        {
            "name": "deterministic_l0_l2",
            "status": "success",
            "duration_ms": det_ms,
            "input_summary": {"kline_count": len(klines)},
            "output_summary": {
                "standard_klines": len(state.get("standard_klines", [])),
                "fractals": len(state.get("fractals", [])),
                "strokes": len(state.get("strokes", [])),
            },
            "error": None,
        }
    ]

    # Phase 2: Run nodes sequentially with tracking
    node_funcs = {
        "segment": segment_node,
        "structure": structure_node,
        "divergence": divergence_node,
        "signal": signal_node,
        "nesting": nesting_node,
    }

    routers = {
        "segment": should_run_structure,
        "structure": should_run_divergence,
        "signal": should_run_nesting,
    }

    current = "segment"
    while current:
        node_fn = node_funcs[current]
        input_sum = _input_summary_for(current, state)
        before = dict(state)

        t1 = time.monotonic()
        try:
            state = node_fn(state)
            elapsed = int((time.monotonic() - t1) * 1000)
            output_diff = _summarize_state_diff(before, state)
            stages.append({
                "name": current,
                "status": "success",
                "duration_ms": elapsed,
                "input_summary": input_sum,
                "output_summary": output_diff,
                "error": None,
            })
        except Exception as exc:
            elapsed = int((time.monotonic() - t1) * 1000)
            stages.append({
                "name": current,
                "status": "error",
                "duration_ms": elapsed,
                "input_summary": input_sum,
                "output_summary": {},
                "error": str(exc),
            })

        # Determine next node via router or linear chain
        if current in routers:
            next_key = routers[current](state)
            if next_key == "end":
                break
            current = next_key
        elif current == "divergence":
            current = "signal"
        elif current == "nesting":
            break
        else:
            break

    return {"result": state, "stages": stages}
