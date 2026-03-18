"""FastAPI gateway for the 缠论 quantitative analysis platform.

Exposes the core analysis pipeline, signal scanning, and backtesting
as REST endpoints.
"""

from __future__ import annotations

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


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Helpers ──────────────────────────────────────────────────────────────────


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
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full L0-L8 analysis pipeline on a single instrument."""
    from chanquant.core.pipeline import AnalysisPipeline

    klines = _parse_klines(req.klines, req.level)
    if not klines:
        raise HTTPException(status_code=400, detail="No klines provided")

    pipeline = AnalysisPipeline()
    state = None
    for bar in klines:
        state = pipeline.feed(bar)

    if state is None:
        raise HTTPException(status_code=400, detail="Pipeline produced no output")

    signals_out: list[SignalOutput] = []
    for sig in state.signals:
        signals_out.append(
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

    return AnalyzeResponse(
        instrument=req.instrument,
        level=req.level,
        kline_count=len(state.standard_klines),
        fractal_count=len(state.fractals),
        stroke_count=len(state.strokes),
        segment_count=len(state.segments),
        center_count=len(state.centers),
        divergence_count=len(state.divergences),
        signals=signals_out,
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
