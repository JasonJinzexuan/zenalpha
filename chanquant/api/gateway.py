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
            state = _run_pipeline(klines)
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
