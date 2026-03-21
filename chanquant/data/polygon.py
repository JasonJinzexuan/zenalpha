"""Polygon.io REST client implementing DataSource protocol."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

import httpx

from chanquant.core.objects import RawKLine, TimeFrame

_TIMEFRAME_MAP: dict[TimeFrame, tuple[int, str]] = {
    TimeFrame.MIN_1: (1, "minute"),
    TimeFrame.MIN_5: (5, "minute"),
    TimeFrame.MIN_30: (30, "minute"),
    TimeFrame.HOUR_1: (1, "hour"),
    TimeFrame.DAILY: (1, "day"),
    TimeFrame.WEEKLY: (1, "week"),
    TimeFrame.MONTHLY: (1, "month"),
}

_BASE_URL = "https://api.polygon.io"
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 0.5  # Unlimited tier


class PolygonClient:
    """Polygon.io market data client with exponential backoff retry."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_klines(
        self,
        instrument: str,
        timeframe: TimeFrame,
        limit: int = 500,
    ) -> Sequence[RawKLine]:
        multiplier, timespan = _TIMEFRAME_MAP[timeframe]
        to_date = datetime.now(tz=timezone.utc)
        from_date = _calculate_from_date(to_date, timeframe, limit)
        return await self._fetch_range(instrument, timeframe, from_date, to_date, limit)

    async def _fetch_range(
        self,
        instrument: str,
        timeframe: TimeFrame,
        from_date: datetime,
        to_date: datetime,
        limit: int,
    ) -> Sequence[RawKLine]:
        multiplier, timespan = _TIMEFRAME_MAP[timeframe]

        all_results: list[dict[str, Any]] = []
        path = (
            f"/v2/aggs/ticker/{instrument}/range"
            f"/{multiplier}/{timespan}"
            f"/{_fmt_date(from_date)}/{_fmt_date(to_date)}"
        )
        params: dict[str, Any] = {"limit": limit, "sort": "asc"}

        while len(all_results) < limit:
            data = await self._request(path, params=params)
            results = data.get("results", [])
            if not results:
                break
            all_results.extend(results)
            next_url = data.get("next_url")
            if not next_url:
                break
            # next_url is absolute; extract path + query for next page
            path, params = _parse_next_url(next_url)

        return tuple(
            _to_raw_kline(bar, timeframe) for bar in all_results[:limit]
        )

    async def get_news(
        self,
        instrument: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch recent news articles. Optionally filter by instrument."""
        params: dict[str, Any] = {
            "limit": limit,
            "sort": "published_utc",
            "order": "desc",
        }
        if instrument:
            params["ticker"] = instrument
        data = await self._request("/v2/reference/news", params=params)
        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "published": r.get("published_utc", ""),
                "tickers": r.get("tickers", []),
                "description": (r.get("description") or "")[:300],
                "source": r.get("publisher", {}).get("name", ""),
            }
            for r in results
        ]

    async def get_instruments(self) -> Sequence[str]:
        data = await self._request(
            "/v3/reference/tickers",
            params={"market": "stocks", "active": "true", "limit": 1000},
        )
        tickers: list[dict[str, Any]] = data.get("results", [])
        return tuple(t["ticker"] for t in tickers)

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        all_params = {"apiKey": self._api_key, **(params or {})}
        backoff = _INITIAL_BACKOFF

        for attempt in range(_MAX_RETRIES):
            resp = await self._client.get(path, params=all_params)
            if resp.status_code == 200:
                return resp.json()  # type: ignore[no-any-return]
            if resp.status_code in (429, 500, 502, 503) and attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(backoff)
                backoff *= 2.0
                continue
            resp.raise_for_status()

        msg = f"Polygon request failed after {_MAX_RETRIES} retries: {path}"
        raise httpx.HTTPError(msg)


def _to_raw_kline(bar: dict[str, Any], timeframe: TimeFrame) -> RawKLine:
    return RawKLine(
        timestamp=datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc),
        open=Decimal(str(bar["o"])),
        high=Decimal(str(bar["h"])),
        low=Decimal(str(bar["l"])),
        close=Decimal(str(bar["c"])),
        volume=int(bar["v"]),
        timeframe=timeframe,
    )


def _calculate_from_date(
    to_date: datetime,
    timeframe: TimeFrame,
    limit: int,
) -> datetime:
    if timeframe == TimeFrame.MONTHLY:
        return to_date - timedelta(days=limit * 31)
    if timeframe == TimeFrame.WEEKLY:
        return to_date - timedelta(weeks=limit)
    if timeframe == TimeFrame.DAILY:
        return to_date - timedelta(days=int(limit * 1.5))  # buffer for weekends/holidays
    multiplier, _ = _TIMEFRAME_MAP[timeframe]
    # For intraday, add buffer for non-trading hours
    return to_date - timedelta(minutes=int(multiplier * limit * 2.5))


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _parse_next_url(next_url: str) -> tuple[str, dict[str, Any]]:
    """Extract path and params from Polygon next_url for pagination."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(next_url)
    path = parsed.path
    qs = parse_qs(parsed.query, keep_blank_values=True)
    params: dict[str, Any] = {k: v[0] for k, v in qs.items()}
    params.pop("apiKey", None)  # _request adds it automatically
    return path, params
