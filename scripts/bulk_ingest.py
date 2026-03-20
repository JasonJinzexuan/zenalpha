"""Bulk historical data ingest: Polygon → InfluxDB.

Run inside the agent pod:
  kubectl cp scripts/bulk_ingest.py zenalpha/<pod>:/tmp/bulk_ingest.py
  kubectl exec -n zenalpha <pod> -- python /tmp/bulk_ingest.py
"""

import asyncio
import os
import sys
import time

INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "PG",
    "MA", "HD", "COST", "ABBV", "CRM",
]

LEVELS = {
    "1w": 2000,
    "1d": 5000,
    "1h": 10000,
    "30m": 10000,
    "5m": 10000,
}


async def main():
    # Import inside to use pod's installed packages
    from chanquant.core.objects import TimeFrame
    from chanquant.data.polygon import PolygonClient
    from chanquant.data.timestream import TimestreamClient

    url = os.environ.get("INFLUXDB_URL", "")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    api_key = os.environ.get("POLYGON_API_KEY", "")

    if not url or not token or not api_key:
        print("ERROR: INFLUXDB_URL, INFLUXDB_TOKEN, POLYGON_API_KEY must be set")
        sys.exit(1)

    ts = TimestreamClient(url=url, token=token)
    pg = PolygonClient(api_key=api_key)

    total = 0
    errors = []
    t0 = time.time()

    for level, limit in LEVELS.items():
        tf = TimeFrame(level)
        print(f"\n=== {level} (limit={limit}) ===")
        for inst in INSTRUMENTS:
            try:
                klines = await pg.get_klines(inst, tf, limit)
                written = await ts.write_klines(inst, tf, klines)
                total += written
                print(f"  {inst}: {written} records")
            except Exception as exc:
                err = f"{inst}:{level} → {exc}"
                errors.append(err)
                print(f"  {inst}: ERROR {exc}")
            await asyncio.sleep(0.1)

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"Done in {elapsed:.0f}s. Total: {total} records.")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

    ts.close()
    await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
