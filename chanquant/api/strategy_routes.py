"""Strategy Lab API routes.

Endpoints for strategy templates, backtesting, sensitivity analysis,
and saving custom strategies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from chanquant.core.objects import RawKLine, TimeFrame
from chanquant.strategy.models import (
    BacktestRequest,
    SensitivityRequest,
    StrategyParams,
    RiskParams,
)
from chanquant.strategy.templates import get_template, list_templates
from chanquant.strategy.evaluator import evaluate_strategy, evaluate_sensitivity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy", tags=["strategy"])

# In-memory store for user-saved strategies (could be InfluxDB later)
_saved_strategies: dict[str, dict] = {}


# ── Models ────────────────────────────────────────────────────────────────────


class TemplateListResponse(BaseModel):
    templates: list[dict[str, Any]]


class BacktestResponse(BaseModel):
    strategy: str
    qualified: bool
    metrics: dict[str, Any]
    qualification: dict[str, Any]
    signal_stats: list[dict[str, Any]]
    trade_count: int
    equity_curve: list[dict[str, str]]
    strategy_params: dict[str, Any]
    risk_params: dict[str, Any]


class SensitivityResponse(BaseModel):
    param_name: str
    results: list[dict[str, Any]]


class SaveStrategyRequest(BaseModel):
    name: str
    strategy: StrategyParams
    risk: RiskParams


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/templates")
async def get_templates() -> TemplateListResponse:
    """List all available strategy templates."""
    templates = list_templates()
    return TemplateListResponse(
        templates=[
            {
                "name": t.name,
                "description": t.description,
                "strategy": t.strategy.model_dump(mode="json"),
                "risk": t.risk.model_dump(mode="json"),
                "qualification_thresholds": {
                    "min_win_rate": str(t.min_win_rate),
                    "min_profit_factor": str(t.min_profit_factor),
                    "max_allowed_drawdown": str(t.max_allowed_drawdown),
                    "min_sharpe": str(t.min_sharpe),
                },
                "qualified": t.qualified,
            }
            for t in templates
        ]
    )


@router.get("/templates/{name}")
async def get_template_detail(name: str):
    """Get a single strategy template by name."""
    if name in _saved_strategies:
        return _saved_strategies[name]

    template = get_template(name)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return {
        "name": template.name,
        "description": template.description,
        "strategy": template.strategy.model_dump(mode="json"),
        "risk": template.risk.model_dump(mode="json"),
    }


@router.post("/backtest")
async def run_backtest(req: BacktestRequest) -> BacktestResponse:
    """Run a strategy backtest.

    Either provide strategy_name (use preset template) or custom strategy/risk params.
    """
    from chanquant.strategy.templates import MODERATE

    if req.strategy_name:
        template = get_template(req.strategy_name)
        if template is None:
            raise HTTPException(
                status_code=404, detail=f"Strategy '{req.strategy_name}' not found"
            )
    elif req.strategy or req.risk:
        update: dict[str, Any] = {"name": "custom"}
        if req.strategy:
            update["strategy"] = req.strategy
        if req.risk:
            update["risk"] = req.risk
        template = MODERATE.model_copy(update=update)
    else:
        template = MODERATE

    multi_klines = await _fetch_backtest_klines(
        req.instruments or _DEFAULT_INSTRUMENTS, req.start_date, req.end_date,
    )

    if not multi_klines:
        raise HTTPException(status_code=400, detail="No kline data available")

    result = await asyncio.to_thread(
        evaluate_strategy, template, multi_klines, req.initial_cash,
    )

    return BacktestResponse(**result)


@router.post("/sensitivity")
async def run_sensitivity(req: SensitivityRequest) -> SensitivityResponse:
    """Run parameter sensitivity analysis."""
    from chanquant.strategy.templates import MODERATE

    base_strategy = req.base_strategy or MODERATE.strategy
    base_risk = req.base_risk or MODERATE.risk
    values = [Decimal(v) for v in req.values]

    multi_klines = await _fetch_backtest_klines(
        req.instruments or _DEFAULT_INSTRUMENTS,
    )
    if not multi_klines:
        raise HTTPException(status_code=400, detail="No kline data available")

    results = await asyncio.to_thread(
        evaluate_sensitivity, base_strategy, base_risk, req.param_name, values, multi_klines,
    )

    return SensitivityResponse(param_name=req.param_name, results=results)


@router.post("/save")
async def save_strategy(req: SaveStrategyRequest):
    """Save a custom strategy template."""
    _saved_strategies[req.name] = {
        "name": req.name,
        "description": "用户自定义策略",
        "strategy": req.strategy.model_dump(mode="json"),
        "risk": req.risk.model_dump(mode="json"),
    }
    return {"saved": True, "name": req.name}


@router.get("/saved")
async def list_saved():
    """List user-saved strategies."""
    return {"strategies": list(_saved_strategies.values())}


# ── Data fetching ────────────────────────────────────────────────────────────

_DEFAULT_INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG", "MA", "HD",
    "COST", "ABBV", "CRM",
]

_TF_MAP = {
    "1w": TimeFrame.WEEKLY,
    "1d": TimeFrame.DAILY,
    "30m": TimeFrame.MIN_30,
    "5m": TimeFrame.MIN_5,
}

_TF_LIMITS = {"1w": 500, "1d": 500, "30m": 2000, "5m": 3000}


async def _fetch_backtest_klines(
    instruments: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, dict[TimeFrame, Sequence[RawKLine]]]:
    """Fetch multi-TF klines from InfluxDB for backtesting.

    Defaults to last 6 months of data if no date range specified.
    """
    import os
    from datetime import datetime, timedelta, timezone
    from chanquant.data.timestream import TimestreamClient

    url = os.environ.get("INFLUXDB_URL", "")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    if not url or not token:
        return {}

    # Default to 6 months
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=180)
    if start_date:
        try:
            cutoff = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Per-TF limits tuned for ~6 months of data
    tf_limits_6mo = {"1w": 26, "1d": 130, "30m": 2000, "5m": 3000}

    ts = TimestreamClient(url=url, token=token)
    try:
        result: dict[str, dict[TimeFrame, Sequence[RawKLine]]] = {}
        for inst in instruments:
            inst_data: dict[TimeFrame, Sequence[RawKLine]] = {}
            for tf_str, tf_enum in _TF_MAP.items():
                limit = tf_limits_6mo.get(tf_str, 500)
                klines = await ts.get_klines(inst, tf_enum, limit)
                if klines:
                    filtered = [
                        k for k in klines
                        if k.timestamp.replace(tzinfo=timezone.utc) >= cutoff
                    ]
                    if filtered:
                        inst_data[tf_enum] = filtered
            if inst_data:
                result[inst] = inst_data
        return result
    finally:
        ts.close()
