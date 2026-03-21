"""Tool definitions for LLM agents with tool use.

Defines callable tools that agents can invoke via Claude's tool_use API.
Each tool has a schema (for LLM) and an execution function (for runtime).
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from typing import Any, Sequence

from chanquant.core.objects import RawKLine, TimeFrame
from chanquant.core.pipeline import AnalysisPipeline


# ── Tool Schemas (for Claude tool_use) ────────────────────────────────────────


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "run_pipeline",
        "description": (
            "Run the deterministic Chan Theory L0-L7 analysis pipeline on K-line data "
            "for a specific instrument and timeframe. Returns fractals, strokes, segments, "
            "centers, trend classification, divergences, and buy/sell signals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument": {
                    "type": "string",
                    "description": "Stock symbol, e.g. 'AAPL'",
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["1w", "1d", "30m", "5m", "1h"],
                    "description": "K-line timeframe",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of K-lines to fetch (default 500)",
                    "default": 500,
                },
            },
            "required": ["instrument", "timeframe"],
        },
    },
    {
        "name": "compare_divergence",
        "description": (
            "Compare MACD areas between two timeframes for the same instrument. "
            "Helps determine if divergence at a larger timeframe is confirmed at smaller level."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument": {
                    "type": "string",
                    "description": "Stock symbol",
                },
                "large_timeframe": {
                    "type": "string",
                    "enum": ["1w", "1d", "30m", "1h"],
                    "description": "Larger timeframe",
                },
                "small_timeframe": {
                    "type": "string",
                    "enum": ["1d", "30m", "5m", "1h"],
                    "description": "Smaller timeframe",
                },
            },
            "required": ["instrument", "large_timeframe", "small_timeframe"],
        },
    },
    {
        "name": "get_market_summary",
        "description": (
            "Get a quick summary of an instrument's current state across all available "
            "timeframes: trend direction, latest signals, center positions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "instrument": {
                    "type": "string",
                    "description": "Stock symbol",
                },
            },
            "required": ["instrument"],
        },
    },
]


# ── Langchain Tool Wrappers (for bind_tools) ─────────────────────────────────


def get_langchain_tools() -> list:
    """Return langchain-compatible tool definitions for bind_tools()."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class RunPipelineInput(BaseModel):
        instrument: str = Field(description="Stock symbol, e.g. 'AAPL'")
        timeframe: str = Field(description="K-line timeframe: 1w, 1d, 30m, 5m, 1h")
        limit: int = Field(default=500, description="Max K-lines to fetch")

    class CompareDivergenceInput(BaseModel):
        instrument: str = Field(description="Stock symbol")
        large_timeframe: str = Field(description="Larger timeframe")
        small_timeframe: str = Field(description="Smaller timeframe")

    class GetMarketSummaryInput(BaseModel):
        instrument: str = Field(description="Stock symbol")

    return [
        StructuredTool(
            name="run_pipeline",
            description=TOOL_SCHEMAS[0]["description"],
            args_schema=RunPipelineInput,
            func=lambda **kwargs: execute_tool("run_pipeline", kwargs),
        ),
        StructuredTool(
            name="compare_divergence",
            description=TOOL_SCHEMAS[1]["description"],
            args_schema=CompareDivergenceInput,
            func=lambda **kwargs: execute_tool("compare_divergence", kwargs),
        ),
        StructuredTool(
            name="get_market_summary",
            description=TOOL_SCHEMAS[2]["description"],
            args_schema=GetMarketSummaryInput,
            func=lambda **kwargs: execute_tool("get_market_summary", kwargs),
        ),
    ]


# ── Tool Execution ────────────────────────────────────────────────────────────

# Cached klines to avoid refetching within a session
_kline_cache: dict[str, list[RawKLine]] = {}


def _cache_key(instrument: str, timeframe: str) -> str:
    return f"{instrument}:{timeframe}"


def _get_klines_sync(instrument: str, timeframe: str, limit: int = 500) -> list[RawKLine]:
    """Fetch klines from InfluxDB (sync wrapper).

    Uses a single shared event loop to avoid asyncio.run() loop-closure issues.
    """
    key = _cache_key(instrument, timeframe)
    if key in _kline_cache:
        return _kline_cache[key]

    url = os.environ.get("INFLUXDB_URL", "")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    if not url or not token:
        return []

    from chanquant.data.timestream import TimestreamClient

    async def _fetch():
        ts = TimestreamClient(url=url, token=token)
        try:
            return list(await ts.get_klines(instrument, TimeFrame(timeframe), limit))
        finally:
            ts.close()

    try:
        klines = _run_async(_fetch())
    except Exception:
        klines = []

    _kline_cache[key] = klines
    return klines


# Shared event loop for sync→async bridge
_shared_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    """Run an async coroutine from sync code, reusing a shared event loop."""
    global _shared_loop

    # If we're inside a running loop (e.g. FastAPI + asyncio.to_thread),
    # create a fresh loop in a thread
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=60)

    # No running loop — use/create a shared loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
    return _shared_loop.run_until_complete(coro)


def _run_pipeline_tool(instrument: str, timeframe: str, limit: int = 500) -> dict[str, Any]:
    """Execute run_pipeline tool: fetch klines + run deterministic L0-L7."""
    klines = _get_klines_sync(instrument, timeframe, limit)
    if not klines:
        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "error": f"No kline data available for {instrument} {timeframe}",
            "bar_count": 0,
        }

    tf = TimeFrame(timeframe)
    pipeline = AnalysisPipeline(level=tf, instrument=instrument)
    state = None
    for bar in klines:
        state = pipeline.feed(bar)

    if state is None:
        return {
            "instrument": instrument,
            "timeframe": timeframe,
            "error": "Pipeline produced no output",
            "bar_count": len(klines),
        }

    signals = []
    for sig in state.signals:
        signals.append({
            "signal_type": sig.signal_type.value,
            "timestamp": sig.timestamp.isoformat(),
            "price": str(sig.price),
            "strength": str(sig.strength),
            "reasoning": sig.reasoning,
        })

    trend_info = None
    if state.trend:
        t = state.trend
        cls_map = {"UP_TREND": "up_trend", "DOWN_TREND": "down_trend", "CONSOLIDATION": "consolidation"}
        trend_info = {
            "classification": cls_map.get(t.classification.name, "unknown"),
            "center_count": len(t.centers),
            "has_segment_c": t.segment_c is not None,
        }

    centers = []
    for c in state.centers:
        centers.append({
            "zg": str(c.zg),
            "zd": str(c.zd),
            "gg": str(c.gg),
            "dd": str(c.dd),
            "start_time": c.start_time.isoformat() if c.start_time else None,
            "end_time": c.end_time.isoformat() if c.end_time else None,
        })

    divergences = []
    for d in state.divergences:
        divergences.append({
            "type": d.type.name.lower(),
            "strength": str(d.strength),
            "a_macd_area": str(d.a_macd_area),
            "c_macd_area": str(d.c_macd_area),
        })

    return {
        "instrument": instrument,
        "timeframe": timeframe,
        "bar_count": len(klines),
        "stroke_count": len(state.strokes),
        "segment_count": len(state.segments),
        "center_count": len(state.centers),
        "divergence_count": len(state.divergences),
        "trend": trend_info,
        "centers": centers,
        "divergences": divergences,
        "signals": signals,
    }


def _compare_divergence_tool(
    instrument: str, large_timeframe: str, small_timeframe: str
) -> dict[str, Any]:
    """Compare divergence status between two timeframes."""
    large_result = _run_pipeline_tool(instrument, large_timeframe)
    small_result = _run_pipeline_tool(instrument, small_timeframe)

    return {
        "instrument": instrument,
        "large_timeframe": {
            "timeframe": large_timeframe,
            "trend": large_result.get("trend"),
            "divergences": large_result.get("divergences", []),
            "signals": large_result.get("signals", []),
        },
        "small_timeframe": {
            "timeframe": small_timeframe,
            "trend": small_result.get("trend"),
            "divergences": small_result.get("divergences", []),
            "signals": small_result.get("signals", []),
        },
        "alignment": _check_alignment(large_result, small_result),
    }


def _check_alignment(large: dict, small: dict) -> dict[str, Any]:
    """Check if large and small timeframe signals align."""
    large_sigs = large.get("signals", [])
    small_sigs = small.get("signals", [])

    def is_buy(s: dict) -> bool:
        return s.get("signal_type", "") in ("B1", "B2", "B3")

    large_direction = None
    if large_sigs:
        large_direction = "buy" if is_buy(large_sigs[-1]) else "sell"

    small_direction = None
    if small_sigs:
        small_direction = "buy" if is_buy(small_sigs[-1]) else "sell"

    aligned = large_direction == small_direction if (large_direction and small_direction) else None

    return {
        "large_direction": large_direction,
        "small_direction": small_direction,
        "aligned": aligned,
        "large_trend": large.get("trend", {}).get("classification") if large.get("trend") else None,
        "small_trend": small.get("trend", {}).get("classification") if small.get("trend") else None,
    }


_TF_LIMITS: dict[str, int] = {
    "1w": 500,
    "1d": 500,
    "1h": 2000,
    "30m": 2000,
    "15m": 3000,
    "5m": 3000,
}


def _get_market_summary_tool(instrument: str) -> dict[str, Any]:
    """Get multi-timeframe summary for an instrument."""
    summary: dict[str, Any] = {"instrument": instrument, "timeframes": {}}

    for tf_str in ["1w", "1d", "30m", "5m"]:
        limit = _TF_LIMITS.get(tf_str, 500)
        result = _run_pipeline_tool(instrument, tf_str, limit)
        summary["timeframes"][tf_str] = {
            "bar_count": result.get("bar_count", 0),
            "trend": result.get("trend"),
            "signals": result.get("signals", []),
            "centers": result.get("centers", []),
            "divergences": result.get("divergences", []),
            "error": result.get("error"),
        }

    return summary


# ── Dispatcher ────────────────────────────────────────────────────────────────


_TOOL_EXECUTORS = {
    "run_pipeline": lambda args: _run_pipeline_tool(
        args["instrument"], args["timeframe"], args.get("limit", 500)
    ),
    "compare_divergence": lambda args: _compare_divergence_tool(
        args["instrument"], args["large_timeframe"], args["small_timeframe"]
    ),
    "get_market_summary": lambda args: _get_market_summary_tool(
        args["instrument"]
    ),
}


def execute_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with given arguments."""
    executor = _TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return executor(args)
    except Exception as exc:
        return {"error": f"Tool execution failed: {exc}"}


def clear_cache() -> None:
    """Clear the kline cache between sessions."""
    _kline_cache.clear()
