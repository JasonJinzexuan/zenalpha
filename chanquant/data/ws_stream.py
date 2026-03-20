"""Polygon/Massive WebSocket streaming client.

Uses the official `massive` SDK for delayed aggregate bars.
Writes 1-min bars to InfluxDB, aggregates into 5m/30m/1h, and runs
Chan Theory analysis every 15 minutes.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from chanquant.core.objects import RawKLine, TimeFrame

logger = logging.getLogger(__name__)

_ANALYSIS_INTERVAL = 900  # 15 minutes

INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG",
    "MA", "HD", "COST", "ABBV", "CRM",
]

# Aggregation periods: (minutes, timeframe_tag)
_AGG_PERIODS = [
    (5, "5m"),
    (30, "30m"),
    (60, "1h"),
]


class BarAggregator:
    """Accumulates 1-min bars and emits higher-TF OHLCV when a period completes."""

    def __init__(self) -> None:
        # sym -> period_tag -> list of 1m RawKLines in current window
        self._buffers: dict[str, dict[str, list[RawKLine]]] = {}

    def add(self, sym: str, kline: RawKLine) -> list[tuple[str, Point]]:
        """Add a 1m bar. Returns list of (timeframe_tag, Point) for completed periods."""
        self._buffers.setdefault(sym, {})
        completed: list[tuple[str, Point]] = []

        minute = kline.timestamp.minute
        hour_minute = kline.timestamp.hour * 60 + minute

        for period, tag in _AGG_PERIODS:
            buf = self._buffers[sym].setdefault(tag, [])
            buf.append(kline)

            # Emit when we hit a period boundary
            is_boundary = (hour_minute + 1) % period == 0
            if is_boundary and buf:
                point = self._flush(sym, tag, buf)
                completed.append((tag, point))
                self._buffers[sym][tag] = []

        return completed

    def _flush(self, sym: str, tag: str, bars: list[RawKLine]) -> Point:
        return (
            Point("kline")
            .tag("instrument", sym)
            .tag("timeframe", tag)
            .field("open", float(bars[0].open))
            .field("high", float(max(b.high for b in bars)))
            .field("low", float(min(b.low for b in bars)))
            .field("close", float(bars[-1].close))
            .field("volume", sum(b.volume for b in bars))
            .time(bars[0].timestamp.replace(tzinfo=timezone.utc), WritePrecision.S)
        )


class StreamWriter:
    """Processes incoming WS bars, writes to InfluxDB, aggregates higher TFs."""

    def __init__(self, influxdb_url: str, influxdb_token: str) -> None:
        self._client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org="zenalpha")
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._aggregator = BarAggregator()
        self._bar_count = 0
        self._last_analysis = 0.0

    def handle_messages(self, msgs: List) -> None:
        for m in msgs:
            try:
                self._process_bar(m)
            except Exception as exc:
                logger.error(f"Error processing bar: {exc}")

        now = time.time()
        if now - self._last_analysis >= _ANALYSIS_INTERVAL:
            self._last_analysis = now
            self._run_analysis()

    def _process_bar(self, m) -> None:
        sym = getattr(m, "symbol", None) or getattr(m, "sym", None)
        if not sym or sym not in INSTRUMENTS:
            return

        ts_ms = getattr(m, "start_timestamp", None) or getattr(m, "s", None)
        if ts_ms is None:
            return

        kline = RawKLine(
            timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None),
            open=Decimal(str(getattr(m, "open", 0) or getattr(m, "o", 0))),
            high=Decimal(str(getattr(m, "high", 0) or getattr(m, "h", 0))),
            low=Decimal(str(getattr(m, "low", 0) or getattr(m, "l", 0))),
            close=Decimal(str(getattr(m, "close", 0) or getattr(m, "c", 0))),
            volume=int(getattr(m, "volume", 0) or getattr(m, "v", 0)),
            timeframe=TimeFrame.MIN_1,
        )

        # 1. Write 1m bar
        point_1m = (
            Point("kline")
            .tag("instrument", sym)
            .tag("timeframe", "1m")
            .field("open", float(kline.open))
            .field("high", float(kline.high))
            .field("low", float(kline.low))
            .field("close", float(kline.close))
            .field("volume", kline.volume)
            .time(kline.timestamp.replace(tzinfo=timezone.utc), WritePrecision.S)
        )

        # 2. Aggregate into 5m/30m/1h
        agg_points = self._aggregator.add(sym, kline)

        # 3. Batch write all points at once
        all_points = [point_1m] + [p for _, p in agg_points]
        try:
            self._write_api.write(bucket="marketdata", org="zenalpha", record=all_points)
        except Exception as exc:
            logger.error(f"Write failed for {sym}: {exc}")
            return

        self._bar_count += 1
        if self._bar_count % 50 == 0:
            logger.info(f"Written {self._bar_count} bars total")

        for tag, _ in agg_points:
            logger.info(f"Aggregated {tag} bar for {sym}")

    def _run_analysis(self) -> None:
        def _analyze():
            logger.info("Running 15-min Chan Theory analysis cycle...")
            from chanquant.agents.tool_defs import execute_tool, clear_cache
            clear_cache()
            for sym in INSTRUMENTS:
                try:
                    result = execute_tool("run_pipeline", {
                        "instrument": sym, "timeframe": "5m", "limit": 500,
                    })
                    signals = result.get("signals", [])
                    if signals:
                        logger.info(f"[{sym}] Signals: {[s['signal_type'] for s in signals]}")
                except Exception as exc:
                    logger.error(f"Analysis error {sym}: {exc}")
            logger.info("Analysis cycle complete.")

        threading.Thread(target=_analyze, daemon=True).start()


_MAX_RETRIES = 20
_INITIAL_BACKOFF = 1.0  # seconds
_MAX_BACKOFF = 300.0  # 5 minutes


def main() -> None:
    from massive import WebSocketClient
    from massive.websocket.models import Feed, Market

    api_key = os.environ.get("POLYGON_API_KEY", "")
    influxdb_url = os.environ.get("INFLUXDB_URL", "")
    influxdb_token = os.environ.get("INFLUXDB_TOKEN", "")

    if not api_key:
        raise RuntimeError("POLYGON_API_KEY not set")
    if not influxdb_url or not influxdb_token:
        raise RuntimeError("INFLUXDB_URL/INFLUXDB_TOKEN not set")

    writer = StreamWriter(influxdb_url=influxdb_url, influxdb_token=influxdb_token)

    backoff = _INITIAL_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            client = WebSocketClient(
                api_key=api_key,
                feed=Feed.Delayed,
                market=Market.Stocks,
            )

            subs = [f"AM.{sym}" for sym in INSTRUMENTS]
            client.subscribe(*subs)

            logger.info(
                f"Starting WebSocket streamer for {len(INSTRUMENTS)} instruments "
                f"(delayed feed, attempt {attempt}/{_MAX_RETRIES})..."
            )
            backoff = _INITIAL_BACKOFF  # reset on successful connect
            client.run(writer.handle_messages)
        except KeyboardInterrupt:
            logger.info("Shutting down WebSocket streamer.")
            break
        except Exception as exc:
            logger.error(f"WebSocket connection error (attempt {attempt}/{_MAX_RETRIES}): {exc}")
            if attempt >= _MAX_RETRIES:
                logger.critical(f"Max retries ({_MAX_RETRIES}) exhausted. Exiting.")
                raise
            logger.info(f"Reconnecting in {backoff:.1f}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
