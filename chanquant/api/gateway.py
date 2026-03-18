"""FastAPI gateway for the 缠论 quantitative analysis platform.

Exposes the core analysis pipeline, signal scanning, and backtesting
as REST endpoints.
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from chanquant.core.objects import RawKLine, TimeFrame

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI is required for the API gateway. "
        "Install it with: pip install fastapi uvicorn"
    )


app = FastAPI(
    title="ZenAlpha - Chan Theory Quantitative Analysis",
    version="0.1.0",
    description="Signal identification and instrument filtering based on Chan Theory (缠论).",
)


# ── Request / Response Models ────────────────────────────────────────────────


class KLineInput(BaseModel):
    timestamp: str  # ISO 8601
    open: str
    high: str
    low: str
    close: str
    volume: int


class AnalyzeRequest(BaseModel):
    instrument: str
    level: str = "1d"
    klines: list[KLineInput]


class SignalOutput(BaseModel):
    signal_type: str
    level: str
    instrument: str
    timestamp: str
    price: str
    strength: str
    source_lesson: str
    reasoning: str


class AnalyzeResponse(BaseModel):
    instrument: str
    level: str
    kline_count: int
    fractal_count: int
    stroke_count: int
    segment_count: int
    center_count: int
    divergence_count: int
    signals: list[SignalOutput]


class BacktestRequest(BaseModel):
    instruments: dict[str, list[KLineInput]]
    initial_cash: str = "1000000"


class BacktestResponse(BaseModel):
    total_return: str
    annualized_return: str
    sharpe_ratio: str
    sortino_ratio: str
    max_drawdown: str
    win_rate: str
    profit_factor: str
    total_trades: int


class ScanRequest(BaseModel):
    instruments: list[str]
    level: str = "1d"
    limit: int = 500


class ScanResultItem(BaseModel):
    instrument: str
    level: str
    kline_count: int
    fractal_count: int
    stroke_count: int
    segment_count: int
    center_count: int
    divergence_count: int
    signals: list[SignalOutput]


class ScanResponse(BaseModel):
    results: list[ScanResultItem]
    source: str  # "timestream" or "polygon"


class IngestRequest(BaseModel):
    instrument: str
    level: str = "1d"
    limit: int = 500


class IngestResponse(BaseModel):
    instrument: str
    level: str
    records_written: int
    source: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestream: str  # "connected" or "not_configured"


# ── Helpers ──────────────────────────────────────────────────────────────────

_INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "")
_INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
_POLYGON_KEY = os.environ.get("POLYGON_API_KEY", "")


def _get_timestream():
    """Lazy-init InfluxDB client. Returns None if not configured."""
    if not _INFLUXDB_URL or not _INFLUXDB_TOKEN:
        return None
    from chanquant.data.timestream import TimestreamClient
    return TimestreamClient(url=_INFLUXDB_URL, token=_INFLUXDB_TOKEN)


def _get_polygon():
    """Lazy-init Polygon client. Returns None if not configured."""
    if not _POLYGON_KEY:
        return None
    from chanquant.data.polygon import PolygonClient
    return PolygonClient(api_key=_POLYGON_KEY)


def _run_pipeline(klines: list[RawKLine]) -> Any:
    """Run the full L0-L8 pipeline on a list of klines."""
    from chanquant.core.pipeline import AnalysisPipeline
    pipeline = AnalysisPipeline()
    state = None
    for bar in klines:
        state = pipeline.feed(bar)
    return state


def _state_to_signals(state: Any) -> list[SignalOutput]:
    """Convert pipeline state signals to SignalOutput list."""
    out: list[SignalOutput] = []
    for sig in state.signals:
        out.append(
            SignalOutput(
                signal_type=sig.signal_type.value,
                level=sig.level.value,
                instrument=sig.instrument,
                timestamp=sig.timestamp.isoformat(),
                price=str(sig.price),
                strength=str(sig.strength),
                source_lesson=sig.source_lesson,
                reasoning=sig.reasoning,
            )
        )
    return out


def _parse_klines(raw: list[KLineInput], level: str) -> list[RawKLine]:
    tf = TimeFrame(level)
    result: list[RawKLine] = []
    for k in raw:
        result.append(
            RawKLine(
                timestamp=datetime.fromisoformat(k.timestamp),
                open=Decimal(k.open),
                high=Decimal(k.high),
                low=Decimal(k.low),
                close=Decimal(k.close),
                volume=k.volume,
                timeframe=tf,
            )
        )
    return result


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    ts_status = "connected" if _INFLUXDB_URL else "not_configured"
    return HealthResponse(status="ok", version="0.2.0", timestream=ts_status)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full L0-L8 analysis pipeline on a single instrument."""
    klines = _parse_klines(req.klines, req.level)
    if not klines:
        raise HTTPException(status_code=400, detail="No klines provided")

    state = _run_pipeline(klines)
    if state is None:
        raise HTTPException(status_code=400, detail="Pipeline produced no output")

    return AnalyzeResponse(
        instrument=req.instrument,
        level=req.level,
        kline_count=len(state.standard_klines),
        fractal_count=len(state.fractals),
        stroke_count=len(state.strokes),
        segment_count=len(state.segments),
        center_count=len(state.centers),
        divergence_count=len(state.divergences),
        signals=_state_to_signals(state),
    )


@app.post("/backtest", response_model=BacktestResponse)
async def backtest(req: BacktestRequest) -> BacktestResponse:
    """Run an event-driven backtest over historical data."""
    from chanquant.backtest.engine import BacktestEngine

    klines_map: dict[str, list[RawKLine]] = {}
    for inst, raw in req.instruments.items():
        klines_map[inst] = _parse_klines(raw, "1d")

    engine = BacktestEngine()
    metrics, _ = engine.run(klines_map, initial_cash=Decimal(req.initial_cash))

    return BacktestResponse(
        total_return=str(metrics.total_return),
        annualized_return=str(metrics.annualized_return),
        sharpe_ratio=str(metrics.sharpe_ratio),
        sortino_ratio=str(metrics.sortino_ratio),
        max_drawdown=str(metrics.max_drawdown),
        win_rate=str(metrics.win_rate),
        profit_factor=str(metrics.profit_factor),
        total_trades=metrics.total_trades,
    )


@app.post("/scan", response_model=ScanResponse)
async def scan(req: ScanRequest) -> ScanResponse:
    """Scan instruments by fetching data from Timestream (or Polygon fallback).

    No need to pass klines — the service fetches data autonomously.
    """
    tf = TimeFrame(req.level)
    ts = _get_timestream()
    pg = _get_polygon()
    source = "none"
    results: list[ScanResultItem] = []

    for instrument in req.instruments:
        klines: list[RawKLine] = []

        # Try Timestream first, then Polygon
        if ts is not None:
            klines = list(await ts.get_klines(instrument, tf, req.limit))
            source = "timestream"

        if not klines and pg is not None:
            klines = list(await pg.get_klines(instrument, tf, req.limit))
            source = "polygon"

        if not klines:
            continue

        state = _run_pipeline(klines)
        if state is None:
            continue

        results.append(
            ScanResultItem(
                instrument=instrument,
                level=req.level,
                kline_count=len(state.standard_klines),
                fractal_count=len(state.fractals),
                stroke_count=len(state.strokes),
                segment_count=len(state.segments),
                center_count=len(state.centers),
                divergence_count=len(state.divergences),
                signals=_state_to_signals(state),
            )
        )

    if ts is not None:
        ts.close()
    if pg is not None:
        await pg.close()

    return ScanResponse(results=results, source=source)


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    """Fetch klines from Polygon and write to Timestream."""
    ts = _get_timestream()
    pg = _get_polygon()

    if ts is None:
        raise HTTPException(status_code=503, detail="TIMESTREAM_DATABASE not configured")
    if pg is None:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY not configured")

    tf = TimeFrame(req.level)
    klines = await pg.get_klines(req.instrument, tf, req.limit)
    written = await ts.write_klines(req.instrument, tf, klines)

    ts.close()
    await pg.close()

    return IngestResponse(
        instrument=req.instrument,
        level=req.level,
        records_written=written,
        source="polygon→timestream",
    )
