"""Decision storage using InfluxDB.

Stores and retrieves trading decisions as time-series data.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_BUCKET = "marketdata"  # reuse existing bucket (token lacks bucket-create permission)
_ORG = "zenalpha"
_MEASUREMENT = "trading_decision"


def _get_client():
    """Create InfluxDB client (lazy)."""
    url = os.environ.get("INFLUXDB_URL", "")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    if not url or not token:
        return None, None, None

    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS

    client = InfluxDBClient(url=url, token=token, org=_ORG)
    return client, client.write_api(write_options=SYNCHRONOUS), client.query_api()


def save_decision(decision: dict[str, Any]) -> bool:
    """Save a trading decision to InfluxDB."""
    client, write_api, _ = _get_client()
    if client is None:
        logger.warning("InfluxDB not configured, skipping decision save")
        return False

    try:
        from influxdb_client import Point, WritePrecision

        point = (
            Point(_MEASUREMENT)
            .tag("instrument", decision["instrument"])
            .tag("action", decision["action"])
            .field("price_range_low", decision.get("price_range_low", ""))
            .field("price_range_high", decision.get("price_range_high", ""))
            .field("stop_loss", decision.get("stop_loss", ""))
            .field("position_size", decision.get("position_size", ""))
            .field("urgency", decision.get("urgency", ""))
            .field("confidence", float(decision.get("confidence", 0)))
            .field("signal_basis", decision.get("signal_basis", ""))
            .field("macro_context", decision.get("macro_context", ""))
            .field("reasoning", decision.get("reasoning", ""))
            .field("nesting_summary", json.dumps(
                decision.get("nesting_summary", {}), default=str, ensure_ascii=False,
            ))
            .field("price_current", decision.get("price_current", ""))
            .time(
                datetime.fromisoformat(decision["timestamp"].replace("Z", "+00:00"))
                if decision.get("timestamp")
                else datetime.now(timezone.utc),
                WritePrecision.S,
            )
        )

        write_api.write(bucket=_BUCKET, org=_ORG, record=point)
        logger.info(f"Saved decision: {decision['instrument']} {decision['action']}")
        return True
    except Exception as exc:
        logger.error(f"Failed to save decision: {exc}")
        return False
    finally:
        client.close()


def get_decisions(
    instrument: str | None = None,
    limit: int = 50,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Retrieve recent decisions from InfluxDB."""
    client, _, query_api = _get_client()
    if client is None:
        return []

    try:
        filter_clause = ""
        if instrument:
            filter_clause = f'|> filter(fn: (r) => r["instrument"] == "{instrument}")'

        query = f'''
from(bucket: "{_BUCKET}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "{_MEASUREMENT}")
  {filter_clause}
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
'''
        tables = query_api.query(query, org=_ORG)
        results: list[dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                vals = record.values
                nesting_raw = vals.get("nesting_summary", "{}")
                try:
                    nesting = json.loads(nesting_raw) if isinstance(nesting_raw, str) else {}
                except json.JSONDecodeError:
                    nesting = {}

                results.append({
                    "instrument": vals.get("instrument", ""),
                    "timestamp": vals.get("_time", "").isoformat() if hasattr(vals.get("_time", ""), "isoformat") else str(vals.get("_time", "")),
                    "action": vals.get("action", ""),
                    "price_current": vals.get("price_current", ""),
                    "price_range_low": vals.get("price_range_low", ""),
                    "price_range_high": vals.get("price_range_high", ""),
                    "stop_loss": vals.get("stop_loss", ""),
                    "position_size": vals.get("position_size", ""),
                    "urgency": vals.get("urgency", ""),
                    "confidence": vals.get("confidence", 0),
                    "signal_basis": vals.get("signal_basis", ""),
                    "macro_context": vals.get("macro_context", ""),
                    "reasoning": vals.get("reasoning", ""),
                    "nesting_summary": nesting,
                })

        return results
    except Exception as exc:
        logger.error(f"Failed to query decisions: {exc}")
        return []
    finally:
        client.close()


def get_latest_decisions(instruments: list[str] | None = None) -> list[dict[str, Any]]:
    """Get the most recent decision for each instrument."""
    all_decisions = get_decisions(limit=200, days=30)

    seen: set[str] = set()
    latest: list[dict[str, Any]] = []
    for d in all_decisions:
        inst = d["instrument"]
        if instruments and inst not in instruments:
            continue
        if inst not in seen:
            seen.add(inst)
            latest.append(d)

    return latest
