"""Shared test fixtures for ZenAlpha."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from chanquant.core.objects import (
    Direction,
    FractalType,
    RawKLine,
    StandardKLine,
    TimeFrame,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[RawKLine]:
    path = FIXTURES_DIR / name
    with open(path) as f:
        data = json.load(f)
    return [
        RawKLine(
            timestamp=datetime.fromisoformat(row["timestamp"]),
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
            volume=int(row["volume"]),
        )
        for row in data
    ]


@pytest.fixture
def uptrend_klines() -> list[RawKLine]:
    return load_fixture("uptrend.json")


@pytest.fixture
def downtrend_klines() -> list[RawKLine]:
    return load_fixture("downtrend.json")


@pytest.fixture
def consolidation_klines() -> list[RawKLine]:
    return load_fixture("consolidation.json")


@pytest.fixture
def simple_up_klines() -> list[StandardKLine]:
    """5 standard klines forming a clear upward move."""
    base_time = datetime(2024, 1, 2)
    return [
        StandardKLine(
            timestamp=datetime(2024, 1, 2),
            open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
            close=Decimal("101"), volume=1000, direction=Direction.UP,
        ),
        StandardKLine(
            timestamp=datetime(2024, 1, 3),
            open=Decimal("101"), high=Decimal("104"), low=Decimal("100"),
            close=Decimal("103"), volume=1100, direction=Direction.UP,
        ),
        StandardKLine(
            timestamp=datetime(2024, 1, 4),
            open=Decimal("103"), high=Decimal("106"), low=Decimal("102"),
            close=Decimal("105"), volume=1200, direction=Direction.UP,
        ),
        StandardKLine(
            timestamp=datetime(2024, 1, 5),
            open=Decimal("105"), high=Decimal("104"), low=Decimal("100"),
            close=Decimal("101"), volume=900, direction=Direction.DOWN,
        ),
        StandardKLine(
            timestamp=datetime(2024, 1, 8),
            open=Decimal("101"), high=Decimal("102"), low=Decimal("98"),
            close=Decimal("99"), volume=1000, direction=Direction.DOWN,
        ),
    ]
