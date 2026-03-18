"""CSV and JSON file loader implementing DataSource protocol."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from chanquant.core.objects import RawKLine, TimeFrame


class CSVLoader:
    """Load backtest data from CSV or JSON files."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def get_klines(
        self,
        instrument: str,
        timeframe: TimeFrame,
        limit: int = 500,
    ) -> Sequence[RawKLine]:
        csv_path = self._data_dir / f"{instrument}.csv"
        json_path = self._data_dir / f"{instrument}.json"

        if csv_path.exists():
            klines = _load_csv(csv_path, timeframe)
        elif json_path.exists():
            klines = _load_json(json_path, timeframe)
        else:
            msg = f"No data file found for {instrument} in {self._data_dir}"
            raise FileNotFoundError(msg)

        return klines[-limit:]

    async def get_instruments(self) -> Sequence[str]:
        stems: list[str] = []
        for path in sorted(self._data_dir.iterdir()):
            if path.suffix in (".csv", ".json"):
                stems.append(path.stem)
        return tuple(dict.fromkeys(stems))


def _load_csv(path: Path, timeframe: TimeFrame) -> tuple[RawKLine, ...]:
    klines: list[RawKLine] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            klines.append(
                RawKLine(
                    timestamp=_parse_timestamp(row["timestamp"]),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=int(row["volume"]),
                    timeframe=timeframe,
                )
            )
    return tuple(klines)


def _load_json(path: Path, timeframe: TimeFrame) -> tuple[RawKLine, ...]:
    data = json.loads(path.read_text())
    klines: list[RawKLine] = []
    for item in data:
        klines.append(
            RawKLine(
                timestamp=_parse_timestamp(item["timestamp"]),
                open=Decimal(str(item["open"])),
                high=Decimal(str(item["high"])),
                low=Decimal(str(item["low"])),
                close=Decimal(str(item["close"])),
                volume=int(item["volume"]),
                timeframe=timeframe,
            )
        )
    return tuple(klines)


def _parse_timestamp(value: str | int | float) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    msg = f"Cannot parse timestamp: {value}"
    raise ValueError(msg)
