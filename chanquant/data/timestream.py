"""Timestream for InfluxDB client implementing DataSource protocol."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from chanquant.core.objects import RawKLine, TimeFrame

_BATCH_SIZE = 5000  # InfluxDB write batch size

# Whitelist patterns for Flux query parameters
_INSTRUMENT_RE = re.compile(r"^[A-Z0-9]{1,10}$")
_VALID_TIMEFRAMES = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"})


def _validate_instrument(instrument: str) -> str:
    """Validate instrument is alphanumeric uppercase, 1-10 chars."""
    if not _INSTRUMENT_RE.match(instrument):
        raise ValueError(f"Invalid instrument: {instrument!r}")
    return instrument


def _validate_timeframe(tf: TimeFrame) -> str:
    """Validate timeframe value against known set."""
    val = tf.value
    if val not in _VALID_TIMEFRAMES:
        raise ValueError(f"Invalid timeframe: {val!r}")
    return val


class TimestreamClient:
    """InfluxDB client for OHLCV K-line storage and retrieval.

    Connects to Amazon Timestream for InfluxDB (managed InfluxDB v2).
    """

    def __init__(
        self,
        url: str,
        token: str,
        org: str = "zenalpha",
        bucket: str = "marketdata",
    ) -> None:
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._org = org
        self._bucket = bucket

    async def get_klines(
        self,
        instrument: str,
        timeframe: TimeFrame,
        limit: int = 500,
    ) -> Sequence[RawKLine]:
        """Query OHLCV data from InfluxDB."""
        safe_instrument = _validate_instrument(instrument)
        safe_tf = _validate_timeframe(timeframe)
        safe_limit = max(1, min(int(limit), 10000))
        flux = (
            f'from(bucket: "{self._bucket}")'
            f' |> range(start: -3650d)'
            f' |> filter(fn: (r) => r._measurement == "kline")'
            f' |> filter(fn: (r) => r.instrument == "{safe_instrument}")'
            f' |> filter(fn: (r) => r.timeframe == "{safe_tf}")'
            f' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
            f' |> sort(columns: ["_time"], desc: true)'
            f' |> limit(n: {safe_limit})'
        )
        tables = await asyncio.to_thread(
            self._client.query_api().query, flux, org=self._org
        )
        rows: list[RawKLine] = []
        for table in tables:
            for record in table.records:
                rows.append(
                    RawKLine(
                        timestamp=record.get_time().replace(tzinfo=None),
                        open=Decimal(str(record.values.get("open", 0))),
                        high=Decimal(str(record.values.get("high", 0))),
                        low=Decimal(str(record.values.get("low", 0))),
                        close=Decimal(str(record.values.get("close", 0))),
                        volume=int(record.values.get("volume", 0)),
                        timeframe=timeframe,
                    )
                )
        return tuple(reversed(rows))  # chronological order

    async def get_instruments(self) -> Sequence[str]:
        """List distinct instruments."""
        flux = (
            f'import "influxdata/influxdb/schema"'
            f'\nschema.tagValues(bucket: "{self._bucket}", tag: "instrument")'
        )
        tables = await asyncio.to_thread(
            self._client.query_api().query, flux, org=self._org
        )
        instruments: list[str] = []
        for table in tables:
            for record in table.records:
                instruments.append(record.get_value())
        return tuple(instruments)

    async def get_latest_timestamp(
        self,
        instrument: str,
        timeframe: TimeFrame,
    ) -> datetime | None:
        """Get the latest timestamp for an instrument/timeframe combo."""
        safe_instrument = _validate_instrument(instrument)
        safe_tf = _validate_timeframe(timeframe)
        flux = (
            f'from(bucket: "{self._bucket}")'
            f' |> range(start: -3650d)'
            f' |> filter(fn: (r) => r._measurement == "kline")'
            f' |> filter(fn: (r) => r.instrument == "{safe_instrument}")'
            f' |> filter(fn: (r) => r.timeframe == "{safe_tf}")'
            f' |> filter(fn: (r) => r._field == "close")'
            f' |> last()'
        )
        tables = await asyncio.to_thread(
            self._client.query_api().query, flux, org=self._org
        )
        for table in tables:
            for record in table.records:
                return record.get_time().replace(tzinfo=None)
        return None

    async def write_klines(
        self,
        instrument: str,
        timeframe: TimeFrame,
        klines: Sequence[RawKLine],
    ) -> int:
        """Write OHLCV records to InfluxDB. Returns count written."""
        write_api = self._client.write_api(write_options=SYNCHRONOUS)
        points = [
            _to_point(k, instrument, timeframe) for k in klines
        ]
        for i in range(0, len(points), _BATCH_SIZE):
            batch = points[i : i + _BATCH_SIZE]
            await asyncio.to_thread(
                write_api.write,
                bucket=self._bucket,
                org=self._org,
                record=batch,
            )
        return len(points)

    def close(self) -> None:
        self._client.close()


def _to_point(k: RawKLine, instrument: str, timeframe: TimeFrame) -> Point:
    """Convert a RawKLine to an InfluxDB Point."""
    ts = k.timestamp.replace(tzinfo=timezone.utc)
    return (
        Point("kline")
        .tag("instrument", instrument)
        .tag("timeframe", timeframe.value)
        .field("open", float(k.open))
        .field("high", float(k.high))
        .field("low", float(k.low))
        .field("close", float(k.close))
        .field("volume", k.volume)
        .time(ts, WritePrecision.S)
    )
