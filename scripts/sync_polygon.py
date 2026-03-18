"""Sync historical K-line data from Polygon.io REST API into MySQL."""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import pymysql

POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_NAME = os.environ.get("DB_NAME", "zenalpha")

BASE_URL = "https://api.polygon.io"

INSTRUMENTS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "UNH", "BRK.B", "XOM", "JNJ", "WMT", "PG",
    "MA", "HD", "COST", "ABBV", "CRM",
]

TIMEFRAMES = {
    "1d": (1, "day"),
    "1h": (1, "hour"),
    "5m": (5, "minute"),
}


def fetch_klines(instrument: str, multiplier: int, timespan: str,
                 from_date: str, to_date: str) -> list[dict]:
    url = (f"{BASE_URL}/v2/aggs/ticker/{instrument}/range/"
           f"{multiplier}/{timespan}/{from_date}/{to_date}"
           f"?adjusted=true&sort=asc&limit=50000&apiKey={POLYGON_API_KEY}")

    for attempt in range(3):
        try:
            resp = urlopen(Request(url), timeout=30)
            data = json.loads(resp.read())
            return data.get("results", [])
        except HTTPError as e:
            if e.code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            raise
    return []


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kline (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                instrument VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) NOT NULL,
                timestamp DATETIME NOT NULL,
                `open` DECIMAL(20,8) NOT NULL,
                high DECIMAL(20,8) NOT NULL,
                low DECIMAL(20,8) NOT NULL,
                `close` DECIMAL(20,8) NOT NULL,
                volume BIGINT NOT NULL,
                UNIQUE KEY uk_kline (instrument, timeframe, timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


def sync_instrument(conn, instrument: str, tf_code: str,
                    multiplier: int, timespan: str, from_date: str, to_date: str) -> int:
    bars = fetch_klines(instrument, multiplier, timespan, from_date, to_date)
    if not bars:
        return 0

    inserted = 0
    with conn.cursor() as cur:
        for bar in bars:
            ts = datetime.utcfromtimestamp(bar["t"] / 1000)
            try:
                cur.execute("""
                    INSERT IGNORE INTO kline (instrument, timeframe, timestamp, `open`, high, low, `close`, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (instrument, tf_code, ts, bar["o"], bar["h"], bar["l"], bar["c"], int(bar["v"])))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                print(f"  Error inserting {instrument} {ts}: {e}")
    conn.commit()
    return inserted


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    instruments = sys.argv[2].split(",") if len(sys.argv) > 2 else INSTRUMENTS

    to_date = datetime.utcnow().strftime("%Y-%m-%d")
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    print(f"Syncing {len(instruments)} instruments, {from_date} → {to_date}")

    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4"
    )
    ensure_table(conn)

    for tf_code, (mult, tspan) in TIMEFRAMES.items():
        if tf_code in ("5m", "1h") and days_back > 30:
            actual_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            actual_from = from_date

        print(f"\n=== Timeframe: {tf_code} ({actual_from} → {to_date}) ===")
        for inst in instruments:
            n = sync_instrument(conn, inst, tf_code, mult, tspan, actual_from, to_date)
            print(f"  {inst}: {n} new bars")
            time.sleep(0.15)  # Polygon rate limit: 5 req/sec free tier

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
