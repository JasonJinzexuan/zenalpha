"""Abstract data source protocol for market data retrieval."""

from __future__ import annotations

from typing import Protocol, Sequence

from chanquant.core.objects import RawKLine, TimeFrame


class DataSource(Protocol):
    """Protocol for market data providers."""

    async def get_klines(
        self,
        instrument: str,
        timeframe: TimeFrame,
        limit: int = 500,
    ) -> Sequence[RawKLine]: ...

    async def get_instruments(self) -> Sequence[str]: ...
