#!/usr/bin/env python3
"""Sync K-line data from Polygon.io into InfluxDB (Timestream).

Usage:
  # Initial backfill — all timeframes, 2 years of daily, 60 days of intraday
  python scripts/sync_polygon_influxdb.py --backfill

  # Daily incremental — fetch yesterday's data for all timeframes
  python scripts/sync_polygon_influxdb.py --daily

  # Custom range
  python scripts/sync_polygon_influxdb.py --from 2024-01-01 --to 2025-03-20 --timeframes 1d,1w

  # Single instrument
  python scripts/sync_polygon_influxdb.py --daily --instruments AAPL

Environment variables:
  POLYGON_API_KEY   — Polygon.io API key (required)
  INFLUXDB_URL      — InfluxDB URL (required)
  INFLUXDB_TOKEN    — InfluxDB token (required)
  INFLUXDB_ORG      — InfluxDB org (default: zenalpha)
  INFLUXDB_BUCKET   — InfluxDB bucket (default: marketdata)
  POLYGON_RATE_SEC  — Max requests per second (default: 4, free tier = 5/min, basic = 5/sec)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# ── Config ──────────────────────────────────────────────────────────────────

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "")
INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "zenalpha")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET", "marketdata")
RATE_LIMIT = float(os.environ.get("POLYGON_RATE_SEC", "4"))  # requests per second

BASE_URL = "https://api.polygon.io"

INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "BRK.B", "XOM", "JNJ", "WMT", "PG",
    "MA", "HD", "COST", "ABBV", "CRM",
]

TIMEFRAME_MAP = {
    "5m":  (5,  "minute"),
    "30m": (30, "minute"),
    "1h":  (1,  "hour"),
    "1d":  (1,  "day"),
    "1w":  (1,  "week"),
}

# How far back to fetch for initial backfill per timeframe
BACKFILL_DAYS = {
    "5m":  14,    # Polygon free: 2 years for aggs, but intraday limited
    "30m": 60,
    "1h":  180,
    "1d":  730,   # ~2 years
    "1w":  1460,  # ~4 years
}

# ── Rate limiter ────────────────────────────────────────────────────────────

_last_request_time = 0.0


def _throttle():
    """Ensure we don't exceed rate limit."""
    global _last_request_time
    min_interval = 1.0 / RATE_LIMIT
    elapsed = time.monotonic() - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.monotonic()


# ── Polygon fetch ───────────────────────────────────────────────────────────


def fetch_klines(
    instrument: str,
    multiplier: int,
    timespan: str,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """Fetch aggregates from Polygon with retry + rate limiting."""
    url = (
        f"{BASE_URL}/v2/aggs/ticker/{instrument}/range/"
        f"{multiplier}/{timespan}/{from_date}/{to_date}"
        f"?adjusted=true&sort=asc&limit=50000&apiKey={POLYGON_API_KEY}"
    )

    for attempt in range(3):
        _throttle()
        try:
            resp = urlopen(Request(url), timeout=30)
            data = json.loads(resp.read())
            return data.get("results", [])
        except HTTPError as e:
            if e.code == 429:
                wait = 12 * (attempt + 1)  # Polygon free tier: wait longer
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if e.code == 403:
                print(f"    403 Forbidden for {instrument}/{timespan} — skipping (plan limit?)")
                return []
            raise
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise
    return []


# ── InfluxDB write ──────────────────────────────────────────────────────────


def write_to_influx(
    write_api,
    instrument: str,
    tf_code: str,
    bars: list[dict],
) -> int:
    """Write bars to InfluxDB. Returns count of points written."""
    points = []
    for bar in bars:
        ts = datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc)
        p = (
            Point("kline")
            .tag("instrument", instrument)
            .tag("timeframe", tf_code)
            .field("open", float(bar["o"]))
            .field("high", float(bar["h"]))
            .field("low", float(bar["l"]))
            .field("close", float(bar["c"]))
            .field("volume", int(bar["v"]))
            .time(ts, WritePrecision.S)
        )
        points.append(p)

    if not points:
        return 0

    # Write in batches of 5000
    batch_size = 5000
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=batch)

    return len(points)


# ── Sync logic ──────────────────────────────────────────────────────────────


def sync_timeframe(
    write_api,
    instruments: list[str],
    tf_code: str,
    from_date: str,
    to_date: str,
) -> int:
    """Sync one timeframe for all instruments. Returns total points written."""
    multiplier, timespan = TIMEFRAME_MAP[tf_code]
    total = 0

    print(f"\n{'='*60}")
    print(f"  Timeframe: {tf_code}  ({from_date} → {to_date})")
    print(f"{'='*60}")

    for inst in instruments:
        bars = fetch_klines(inst, multiplier, timespan, from_date, to_date)
        if bars:
            n = write_to_influx(write_api, inst, tf_code, bars)
            total += n
            print(f"  {inst:8s}: {n:5d} bars")
        else:
            print(f"  {inst:8s}:     0 bars (no data)")

    return total


def run_backfill(instruments: list[str], timeframes: list[str]):
    """Initial backfill: fetch historical data for all timeframes."""
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    to_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    grand_total = 0

    for tf in timeframes:
        days = BACKFILL_DAYS.get(tf, 365)
        from_date = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        n = sync_timeframe(write_api, instruments, tf, from_date, to_date)
        grand_total += n

    client.close()
    print(f"\nBackfill complete: {grand_total} total points written")


def run_daily(instruments: list[str], timeframes: list[str]):
    """Daily incremental: fetch previous day's data."""
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    now = datetime.now(tz=timezone.utc)
    to_date = now.strftime("%Y-%m-%d")
    # Fetch 3 days back to handle weekends/gaps
    from_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    grand_total = 0

    for tf in timeframes:
        n = sync_timeframe(write_api, instruments, tf, from_date, to_date)
        grand_total += n

    client.close()
    print(f"\nDaily sync complete: {grand_total} total points written")


def run_custom(
    instruments: list[str],
    timeframes: list[str],
    from_date: str,
    to_date: str,
):
    """Custom date range sync."""
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    grand_total = 0
    for tf in timeframes:
        n = sync_timeframe(write_api, instruments, tf, from_date, to_date)
        grand_total += n

    client.close()
    print(f"\nCustom sync complete: {grand_total} total points written")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Sync Polygon → InfluxDB")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", action="store_true", help="Initial historical backfill")
    mode.add_argument("--daily", action="store_true", help="Daily incremental sync")
    mode.add_argument("--from", dest="from_date", help="Custom from date (YYYY-MM-DD)")

    parser.add_argument("--to", dest="to_date", help="Custom to date (YYYY-MM-DD)")
    parser.add_argument("--instruments", help="Comma-separated instruments (default: all 20)")
    parser.add_argument("--timeframes", help="Comma-separated timeframes (default: 5m,30m,1h,1d,1w)")

    args = parser.parse_args()

    # Validate env
    if not POLYGON_API_KEY:
        print("ERROR: POLYGON_API_KEY not set")
        sys.exit(1)
    if not INFLUXDB_URL or not INFLUXDB_TOKEN:
        print("ERROR: INFLUXDB_URL and INFLUXDB_TOKEN must be set")
        sys.exit(1)

    instruments = args.instruments.split(",") if args.instruments else INSTRUMENTS
    timeframes = args.timeframes.split(",") if args.timeframes else list(TIMEFRAME_MAP.keys())

    # Validate timeframes
    for tf in timeframes:
        if tf not in TIMEFRAME_MAP:
            print(f"ERROR: Unknown timeframe '{tf}'. Valid: {list(TIMEFRAME_MAP.keys())}")
            sys.exit(1)

    print(f"Instruments: {len(instruments)} | Timeframes: {timeframes}")
    print(f"Rate limit: {RATE_LIMIT} req/sec")
    est_calls = len(instruments) * len(timeframes)
    est_time = est_calls / RATE_LIMIT
    print(f"Estimated API calls: {est_calls} (~{est_time:.0f}s)")

    if args.backfill:
        run_backfill(instruments, timeframes)
    elif args.daily:
        run_daily(instruments, timeframes)
    elif args.from_date:
        to_date = args.to_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        run_custom(instruments, timeframes, args.from_date, to_date)


if __name__ == "__main__":
    main()
