"""FastAPI gateway for the 缠论 quantitative analysis platform.

Exposes the core analysis pipeline, signal scanning, and backtesting
as REST endpoints.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from chanquant.core.objects import RawKLine, TimeFrame

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
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


# ── Simple in-memory rate limiter (no extra dependency) ──────────────────────

import time
from collections import defaultdict

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMITS: dict[str, int] = {
    "default": 60,       # 60 req/min general
    "/ingest": 10,       # 10 req/min for heavy ingest ops
    "/pipeline": 20,     # 20 req/min for LLM pipelines
    "/nesting": 10,      # 10 req/min for nesting analysis
    "/scan": 10,         # 10 req/min for scans
}
_request_counts: dict[str, list[float]] = defaultdict(list)


def _get_rate_limit(path: str) -> int:
    for prefix, limit in _RATE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return limit
    return _RATE_LIMITS["default"]


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path
    limit = _get_rate_limit(path)
    key = f"{client_ip}:{path.split('/')[1] if '/' in path[1:] else path}"

    now = time.time()
    timestamps = _request_counts[key]
    # Prune old entries
    _request_counts[key] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]

    if len(_request_counts[key]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )

    _request_counts[key].append(now)
    return await call_next(request)


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


class FractalOutput(BaseModel):
    type: str  # "top" or "bottom"
    timestamp: str
    price: str
    kline_index: int


class StrokeOutput(BaseModel):
    direction: str  # "up" or "down"
    start_index: int
    end_index: int
    start_price: str
    end_price: str
    start_time: str
    end_time: str
    kline_count: int
    macd_area: str


class SegmentOutput(BaseModel):
    direction: str
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    high: str
    low: str
    stroke_count: int
    termination_type: str  # "first" or "second"


class CenterOutput(BaseModel):
    zg: str
    zd: str
    gg: str
    dd: str
    start_time: str
    end_time: str
    extension_count: int


class DivergenceOutput(BaseModel):
    type: str  # "trend" or "consolidation"
    a_macd_area: str
    c_macd_area: str
    a_dif_peak: str
    c_dif_peak: str
    area_ratio: str
    strength: str


class MACDOutput(BaseModel):
    dif: str
    dea: str
    histogram: str


class TrendOutput(BaseModel):
    classification: str  # "up_trend" / "down_trend" / "consolidation"
    center_count: int
    has_segment_c: bool
    walk_state: str  # derived: up_trend / down_trend / consolidation / c_extending / top_divergence / bottom_divergence


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
    fractals: list[FractalOutput] = []
    strokes: list[StrokeOutput] = []
    segments: list[SegmentOutput] = []
    centers: list[CenterOutput] = []
    divergences: list[DivergenceOutput] = []
    macd_values: list[MACDOutput] = []
    trend: TrendOutput | None = None


class BacktestRequest(BaseModel):
    instruments: dict[str, list[KLineInput]]
    initial_cash: str = "1000000"
    level: str = "1d"


class NestingBacktestRequest(BaseModel):
    instruments: list[str]
    initial_cash: str = "1000000"
    levels: list[str] = ["1w", "1d", "30m", "5m"]
    exec_level: str = "1d"
    limit: int = 500
    min_nesting_depth: int = 2
    require_alignment: bool = True


class TradeLogEntry(BaseModel):
    action: str
    instrument: str
    timestamp: str
    price: str
    signal: str
    nesting_depth: int
    aligned: bool
    large: str | None = None
    medium: str | None = None
    precise: str | None = None


class BacktestResponse(BaseModel):
    total_return: str
    annualized_return: str
    sharpe_ratio: str
    sortino_ratio: str
    max_drawdown: str
    win_rate: str
    profit_factor: str
    total_trades: int
    trade_log: list[TradeLogEntry] = []


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
    fractals: list[FractalOutput] = []
    strokes: list[StrokeOutput] = []
    segments: list[SegmentOutput] = []
    centers: list[CenterOutput] = []
    divergences: list[DivergenceOutput] = []
    macd_values: list[MACDOutput] = []
    trend: TrendOutput | None = None


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


class KLineOutput(BaseModel):
    timestamp: str
    open: str
    high: str
    low: str
    close: str
    volume: int


class KLineResponse(BaseModel):
    instrument: str
    level: str
    klines: list[KLineOutput]


class HealthResponse(BaseModel):
    status: str
    version: str
    timestream: str  # "connected" or "not_configured"


# ── Helpers ──────────────────────────────────────────────────────────────────

_INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "")
_INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
_POLYGON_KEY = os.environ.get("POLYGON_API_KEY", "")
_DATA_SERVICE_URL = os.environ.get("DATA_SERVICE_URL", "http://data-service:8083")

import re

_INSTRUMENT_RE = re.compile(r"^[A-Z0-9]{1,10}$")
_VALID_LEVELS = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"})


def _validate_instrument(instrument: str) -> str:
    if not _INSTRUMENT_RE.match(instrument):
        raise HTTPException(status_code=400, detail=f"Invalid instrument: {instrument!r}")
    return instrument


def _validate_level(level: str) -> str:
    if level not in _VALID_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid level: {level!r}")
    return level


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


def _run_pipeline(klines: list[RawKLine], instrument: str = "", level: str = "1d") -> Any:
    """Run the full L0-L8 pipeline on a list of klines."""
    from chanquant.core.pipeline import AnalysisPipeline
    from chanquant.core.objects import TimeFrame
    pipeline = AnalysisPipeline(level=TimeFrame(level), instrument=instrument)
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


def _state_to_fractals(state: Any) -> list[FractalOutput]:
    return [
        FractalOutput(
            type="top" if f.type.name == "TOP" else "bottom",
            timestamp=f.timestamp.isoformat(),
            price=str(f.extreme_value),
            kline_index=f.kline_index,
        )
        for f in state.fractals
    ]


def _state_to_strokes(state: Any) -> list[StrokeOutput]:
    return [
        StrokeOutput(
            direction="up" if s.direction.name == "UP" else "down",
            start_index=s.start_fractal.kline_index,
            end_index=s.end_fractal.kline_index,
            start_price=str(s.start_fractal.extreme_value),
            end_price=str(s.end_fractal.extreme_value),
            start_time=s.start_fractal.timestamp.isoformat(),
            end_time=s.end_fractal.timestamp.isoformat(),
            kline_count=s.kline_count,
            macd_area=str(s.macd_area),
        )
        for s in state.strokes
    ]


def _state_to_segments(state: Any) -> list[SegmentOutput]:
    return [
        SegmentOutput(
            direction="up" if seg.direction.name == "UP" else "down",
            start_index=seg.strokes[0].start_fractal.kline_index if seg.strokes else 0,
            end_index=seg.strokes[-1].end_fractal.kline_index if seg.strokes else 0,
            start_time=seg.start_time.isoformat() if seg.start_time else "",
            end_time=seg.end_time.isoformat() if seg.end_time else "",
            high=str(seg.high),
            low=str(seg.low),
            stroke_count=seg.stroke_count,
            termination_type="first" if seg.termination_type.name == "FIRST_KIND" else "second",
        )
        for seg in state.segments
    ]


def _state_to_centers(state: Any) -> list[CenterOutput]:
    return [
        CenterOutput(
            zg=str(c.zg),
            zd=str(c.zd),
            gg=str(c.gg),
            dd=str(c.dd),
            start_time=c.start_time.isoformat() if c.start_time else "",
            end_time=c.end_time.isoformat() if c.end_time else "",
            extension_count=c.extension_count,
        )
        for c in state.centers
    ]


def _state_to_divergences(state: Any) -> list[DivergenceOutput]:
    return [
        DivergenceOutput(
            type="trend" if d.type.name == "TREND" else "consolidation",
            a_macd_area=str(d.a_macd_area),
            c_macd_area=str(d.c_macd_area),
            a_dif_peak=str(d.a_dif_peak),
            c_dif_peak=str(d.c_dif_peak),
            area_ratio=str(d.area_ratio),
            strength=str(d.strength),
        )
        for d in state.divergences
    ]


def _state_to_macd(state: Any) -> list[MACDOutput]:
    return [
        MACDOutput(dif=str(m.dif), dea=str(m.dea), histogram=str(m.histogram))
        for m in state.macd_values
    ]


def _state_to_trend(state: Any) -> TrendOutput | None:
    if state.trend is None:
        return None
    t = state.trend
    cls_map = {"UP_TREND": "up_trend", "DOWN_TREND": "down_trend", "CONSOLIDATION": "consolidation"}
    classification = cls_map.get(t.classification.name, "consolidation")

    # Derive walk_state
    walk_state = classification
    has_div = len(state.divergences) > 0
    has_c = t.segment_c is not None
    if has_c and not has_div:
        walk_state = "c_extending"
    elif has_div and classification == "up_trend":
        walk_state = "top_divergence"
    elif has_div and classification == "down_trend":
        walk_state = "bottom_divergence"

    return TrendOutput(
        classification=classification,
        center_count=len(t.centers),
        has_segment_c=has_c,
        walk_state=walk_state,
    )


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


@app.get("/klines/{instrument}", response_model=KLineResponse)
async def get_klines(instrument: str, level: str = "1d", limit: int = 500) -> KLineResponse:
    """Fetch raw K-line data from Timestream (InfluxDB)."""
    _validate_instrument(instrument)
    _validate_level(level)
    tf = TimeFrame(level)
    ts = _get_timestream()
    if ts is None:
        raise HTTPException(status_code=503, detail="INFLUXDB not configured")
    try:
        klines = list(await ts.get_klines(instrument, tf, limit))
    finally:
        ts.close()
    return KLineResponse(
        instrument=instrument,
        level=level,
        klines=[
            KLineOutput(
                timestamp=k.timestamp.isoformat(),
                open=str(k.open),
                high=str(k.high),
                low=str(k.low),
                close=str(k.close),
                volume=k.volume,
            )
            for k in klines
        ],
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full L0-L8 analysis pipeline on a single instrument."""
    klines = _parse_klines(req.klines, req.level)
    if not klines:
        raise HTTPException(status_code=400, detail="No klines provided")

    state = _run_pipeline(klines, instrument=req.instrument, level=req.level)
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
        fractals=_state_to_fractals(state),
        strokes=_state_to_strokes(state),
        segments=_state_to_segments(state),
        centers=_state_to_centers(state),
        divergences=_state_to_divergences(state),
        macd_values=_state_to_macd(state),
        trend=_state_to_trend(state),
    )


@app.post("/backtest", response_model=BacktestResponse)
async def backtest(req: BacktestRequest) -> BacktestResponse:
    """Run an event-driven backtest over historical data."""
    from chanquant.backtest.engine import BacktestEngine

    klines_map: dict[str, list[RawKLine]] = {}
    for inst, raw in req.instruments.items():
        klines_map[inst] = _parse_klines(raw, req.level)

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


@app.post("/backtest/nesting", response_model=BacktestResponse)
async def backtest_nesting(req: NestingBacktestRequest) -> BacktestResponse:
    """Multi-timeframe nesting backtest. Fetches data from InfluxDB automatically."""
    from chanquant.backtest.nesting_engine import NestingBacktestEngine

    ts = _get_timestream()
    if ts is None:
        raise HTTPException(status_code=503, detail="INFLUXDB not configured")

    try:
        multi_klines: dict[str, dict[TimeFrame, list[RawKLine]]] = {}
        for inst in req.instruments:
            multi_klines[inst] = {}
            for level_str in req.levels:
                tf = TimeFrame(level_str)
                try:
                    klines = list(await ts.get_klines(inst, tf, req.limit))
                    if klines:
                        multi_klines[inst][tf] = klines
                except Exception:
                    pass  # skip unavailable timeframes
            if not multi_klines[inst]:
                del multi_klines[inst]
    finally:
        ts.close()

    if not multi_klines:
        raise HTTPException(
            status_code=400,
            detail="No kline data available for any instrument/timeframe combination",
        )

    engine = NestingBacktestEngine(
        min_nesting_depth=req.min_nesting_depth,
        require_alignment=req.require_alignment,
    )
    exec_tf = TimeFrame(req.exec_level)
    metrics, _, trade_log = engine.run(
        multi_klines,
        initial_cash=Decimal(req.initial_cash),
        exec_level=exec_tf,
    )

    return BacktestResponse(
        total_return=str(metrics.total_return),
        annualized_return=str(metrics.annualized_return),
        sharpe_ratio=str(metrics.sharpe_ratio),
        sortino_ratio=str(metrics.sortino_ratio),
        max_drawdown=str(metrics.max_drawdown),
        win_rate=str(metrics.win_rate),
        profit_factor=str(metrics.profit_factor),
        total_trades=metrics.total_trades,
        trade_log=[TradeLogEntry(**t) for t in trade_log],
    )


class NestingAnalysisRequest(BaseModel):
    instrument: str
    use_llm: bool = True


class NestingAnalysisResponse(BaseModel):
    instrument: str
    nesting_path: list[str] = []
    target_level: str = ""
    large_signal: str | None = None
    medium_signal: str | None = None
    precise_signal: str | None = None
    nesting_depth: int = 0
    direction_aligned: bool = False
    confidence: str = "0"
    confidence_source: str = ""
    reasoning: str = ""
    risk_assessment: str = ""
    tool_calls: list[dict] = []
    iterations: int = 0


@app.post("/nesting/analyze", response_model=NestingAnalysisResponse)
async def nesting_analyze(req: NestingAnalysisRequest) -> NestingAnalysisResponse:
    """Run multi-timeframe nesting analysis with LLM tool use.

    The agent autonomously fetches data for 1w/1d/30m/5m,
    runs pipelines, and synthesizes nesting analysis.
    """
    _validate_instrument(req.instrument)
    from chanquant.agents.nester import NesterAgent

    nester = NesterAgent(use_llm=req.use_llm)
    result = await asyncio.to_thread(nester.analyze_instrument, req.instrument)

    if result is None:
        return NestingAnalysisResponse(instrument=req.instrument)

    return NestingAnalysisResponse(
        instrument=result.get("instrument", req.instrument),
        nesting_path=result.get("nesting_path", []),
        target_level=result.get("target_level", ""),
        large_signal=result.get("large_signal"),
        medium_signal=result.get("medium_signal"),
        precise_signal=result.get("precise_signal"),
        nesting_depth=result.get("nesting_depth", 0),
        direction_aligned=result.get("direction_aligned", False),
        confidence=str(result.get("confidence", "0")),
        confidence_source=result.get("confidence_source", ""),
        reasoning=result.get("reasoning", ""),
        risk_assessment=result.get("risk_assessment", ""),
        tool_calls=result.get("tool_calls", []),
        iterations=result.get("iterations", 0),
    )


@app.post("/scan", response_model=ScanResponse)
async def scan(req: ScanRequest) -> ScanResponse:
    """Scan instruments by fetching data from Timestream (or Polygon fallback).

    No need to pass klines — the service fetches data autonomously.
    """
    _validate_level(req.level)
    for inst in req.instruments:
        _validate_instrument(inst)
    tf = TimeFrame(req.level)
    ts = _get_timestream()
    pg = _get_polygon()
    source = "none"
    results: list[ScanResultItem] = []

    for instrument in req.instruments:
        klines: list[RawKLine] = []

        # Try Timestream first, then Polygon fallback
        if ts is not None:
            try:
                klines = list(await ts.get_klines(instrument, tf, req.limit))
                source = "timestream"
            except Exception:
                pass  # fallback to polygon

        if not klines and pg is not None:
            try:
                klines = list(await pg.get_klines(instrument, tf, req.limit))
                source = "polygon"
            except Exception:
                pass  # skip this instrument on Polygon failure

        if not klines:
            continue

        try:
            state = _run_pipeline(klines, instrument=instrument, level=req.level)
        except Exception:
            continue
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
                fractals=_state_to_fractals(state),
                strokes=_state_to_strokes(state),
                segments=_state_to_segments(state),
                centers=_state_to_centers(state),
                divergences=_state_to_divergences(state),
                macd_values=_state_to_macd(state),
                trend=_state_to_trend(state),
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
    _validate_instrument(req.instrument)
    _validate_level(req.level)
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


_DEFAULT_INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG",
    "MA", "HD", "COST", "ABBV", "CRM",
]

_BULK_LIMITS: dict[str, int] = {
    "5m": 50000,
    "30m": 50000,
    "1h": 50000,
    "1d": 5000,
    "1w": 2000,
}


class BulkIngestRequest(BaseModel):
    instruments: list[str] = _DEFAULT_INSTRUMENTS
    levels: list[str] = ["5m", "30m", "1h", "1d", "1w"]
    limit: int | None = None  # None = use per-level defaults


class BulkIngestResponse(BaseModel):
    total_written: int
    details: list[dict]
    source: str


@app.post("/ingest/bulk", response_model=BulkIngestResponse)
async def ingest_bulk(req: BulkIngestRequest) -> BulkIngestResponse:
    """Bulk ingest: fetch all timeframes for all instruments from Polygon → Timestream."""
    ts = _get_timestream()
    pg = _get_polygon()

    if ts is None:
        raise HTTPException(status_code=503, detail="INFLUXDB not configured")
    if pg is None:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY not configured")

    total = 0
    details: list[dict] = []

    for level in req.levels:
        tf = TimeFrame(level)
        limit = req.limit if req.limit is not None else _BULK_LIMITS.get(level, 5000)
        for instrument in req.instruments:
            try:
                klines = await pg.get_klines(instrument, tf, limit)
                written = await ts.write_klines(instrument, tf, klines)
                total += written
                details.append({
                    "instrument": instrument,
                    "level": level,
                    "records_written": written,
                })
            except Exception as exc:
                details.append({
                    "instrument": instrument,
                    "level": level,
                    "records_written": 0,
                    "error": str(exc),
                })
            await asyncio.sleep(0.1)  # small courtesy delay

    ts.close()
    await pg.close()

    return BulkIngestResponse(
        total_written=total,
        details=details,
        source="polygon→timestream",
    )


class SyncIngestRequest(BaseModel):
    instruments: list[str] = _DEFAULT_INSTRUMENTS
    levels: list[str] = ["5m", "30m", "1h", "1d", "1w"]


class SyncIngestResponse(BaseModel):
    total_written: int
    details: list[dict]


@app.post("/ingest/sync", response_model=SyncIngestResponse)
async def ingest_sync(req: SyncIngestRequest) -> SyncIngestResponse:
    """Incremental sync: fetch only new data since last ingested timestamp."""
    ts = _get_timestream()
    pg = _get_polygon()

    if ts is None:
        raise HTTPException(status_code=503, detail="INFLUXDB not configured")
    if pg is None:
        raise HTTPException(status_code=503, detail="POLYGON_API_KEY not configured")

    total = 0
    details: list[dict] = []

    for level in req.levels:
        tf = TimeFrame(level)
        for instrument in req.instruments:
            try:
                latest = await ts.get_latest_timestamp(instrument, tf)
                if latest is None:
                    # No data yet — do a full pull
                    limit = _BULK_LIMITS.get(level, 5000)
                else:
                    # Calculate bars since last timestamp
                    from datetime import timezone as tz
                    now = datetime.now(tz=tz.utc).replace(tzinfo=None)
                    delta = now - latest
                    limit = _estimate_bars_needed(delta, level)
                    if limit < 2:
                        details.append({
                            "instrument": instrument,
                            "level": level,
                            "records_written": 0,
                            "status": "up_to_date",
                        })
                        continue

                klines = await pg.get_klines(instrument, tf, limit)
                written = await ts.write_klines(instrument, tf, klines)
                total += written
                details.append({
                    "instrument": instrument,
                    "level": level,
                    "records_written": written,
                    "last_before": latest.isoformat() if latest else None,
                })
            except Exception as exc:
                details.append({
                    "instrument": instrument,
                    "level": level,
                    "records_written": 0,
                    "error": str(exc),
                })
            await asyncio.sleep(0.1)

    ts.close()
    await pg.close()

    return SyncIngestResponse(total_written=total, details=details)


def _estimate_bars_needed(delta: "timedelta", level: str) -> int:
    """Estimate how many bars to fetch based on time gap and level."""
    from datetime import timedelta
    total_minutes = delta.total_seconds() / 60
    if level == "5m":
        return min(50000, int(total_minutes / 5) + 10)
    elif level == "30m":
        return min(50000, int(total_minutes / 30) + 10)
    elif level == "1h":
        return min(50000, int(total_minutes / 60) + 10)
    elif level == "1d":
        return min(5000, int(delta.days * 1.5) + 10)
    elif level == "1w":
        return min(2000, int(delta.days / 7) + 10)
    return 500


# ── LangGraph LLM Pipeline (async task system) ────────────────────────────


class StageOutput(BaseModel):
    name: str
    status: str
    duration_ms: int
    input_summary: dict = {}
    output_summary: dict = {}
    error: str | None = None


class PipelineItemStatus(BaseModel):
    instrument: str
    status: str  # "pending" | "running" | "done" | "error"
    level: str = "1d"
    kline_count: int = 0
    segments: list[dict] = []
    centers: list[dict] = []
    trend: dict | None = None
    divergence: dict | None = None
    signals: list[dict] = []
    nesting: dict | None = None
    errors: list[str] = []
    stages: list[StageOutput] = []
    total_duration_ms: int = 0
    updated_at: str = ""


class PipelineTriggerRequest(BaseModel):
    instruments: list[str]
    level: str = "1d"
    limit: int = 300


class PipelineTriggerResponse(BaseModel):
    triggered: int
    instruments: list[str]


class PipelineStatusResponse(BaseModel):
    items: list[PipelineItemStatus]


# In-memory pipeline result cache
_pipeline_cache: dict[str, dict] = {}


def _cache_key(instrument: str, level: str) -> str:
    return f"{instrument}:{level}"


async def _run_pipeline_task(instrument: str, level: str, limit: int) -> None:
    """Background task: fetch klines, run LLM pipeline, store result."""
    key = _cache_key(instrument, level)
    _pipeline_cache[key] = {
        "instrument": instrument,
        "status": "running",
        "level": level,
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        tf = TimeFrame(level)
        ts = _get_timestream()
        if ts is None:
            raise RuntimeError("INFLUXDB not configured")
        try:
            klines = list(await ts.get_klines(instrument, tf, limit))
        finally:
            ts.close()

        if not klines:
            _pipeline_cache[key] = {
                "instrument": instrument,
                "status": "error",
                "level": level,
                "errors": [f"No klines for {instrument}"],
                "updated_at": datetime.utcnow().isoformat(),
            }
            return

        from chanquant.agents.langgraph_pipeline import run_llm_analysis_with_stages

        data = await asyncio.to_thread(
            run_llm_analysis_with_stages, klines, instrument=instrument, level=level
        )

        result = data["result"]
        stages_raw = data["stages"]
        total_ms = sum(s["duration_ms"] for s in stages_raw)

        _pipeline_cache[key] = {
            "instrument": instrument,
            "status": "done",
            "level": level,
            "kline_count": len(klines),
            "segments": result.get("segments", []),
            "centers": result.get("centers", []),
            "trend": result.get("trend"),
            "divergence": result.get("divergence"),
            "signals": result.get("signals", []),
            "nesting": result.get("nesting"),
            "errors": result.get("errors", []),
            "stages": [dict(s) for s in stages_raw],
            "total_duration_ms": total_ms,
            "updated_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        _pipeline_cache[key] = {
            "instrument": instrument,
            "status": "error",
            "level": level,
            "errors": [str(exc)],
            "updated_at": datetime.utcnow().isoformat(),
        }


@app.post("/pipeline/trigger", response_model=PipelineTriggerResponse)
async def pipeline_trigger(req: PipelineTriggerRequest) -> PipelineTriggerResponse:
    """Trigger LLM pipeline analysis for multiple instruments. Returns immediately."""
    triggered: list[str] = []
    for instrument in req.instruments:
        key = _cache_key(instrument, req.level)
        existing = _pipeline_cache.get(key, {})
        if existing.get("status") == "running":
            continue  # skip already running
        _pipeline_cache[key] = {
            "instrument": instrument,
            "status": "pending",
            "level": req.level,
            "updated_at": datetime.utcnow().isoformat(),
        }
        asyncio.create_task(_run_pipeline_task(instrument, req.level, req.limit))
        triggered.append(instrument)

    return PipelineTriggerResponse(triggered=len(triggered), instruments=triggered)


@app.get("/pipeline/status", response_model=PipelineStatusResponse)
async def pipeline_status(instruments: str = "", level: str = "1d") -> PipelineStatusResponse:
    """Get pipeline status for instruments (comma-separated). Returns cached results."""
    items: list[PipelineItemStatus] = []
    if instruments:
        symbols = [s.strip() for s in instruments.split(",") if s.strip()]
    else:
        symbols = list({v["instrument"] for v in _pipeline_cache.values()})

    for sym in symbols:
        key = _cache_key(sym, level)
        cached = _pipeline_cache.get(key)
        if cached:
            stages = [StageOutput(**s) for s in cached.get("stages", [])]
            items.append(PipelineItemStatus(
                instrument=cached.get("instrument", sym),
                status=cached.get("status", "pending"),
                level=cached.get("level", level),
                kline_count=cached.get("kline_count", 0),
                segments=cached.get("segments", []),
                centers=cached.get("centers", []),
                trend=cached.get("trend"),
                divergence=cached.get("divergence"),
                signals=cached.get("signals", []),
                nesting=cached.get("nesting"),
                errors=cached.get("errors", []),
                stages=stages,
                total_duration_ms=cached.get("total_duration_ms", 0),
                updated_at=cached.get("updated_at", ""),
            ))
        else:
            items.append(PipelineItemStatus(instrument=sym, status="idle", level=level))

    return PipelineStatusResponse(items=items)
