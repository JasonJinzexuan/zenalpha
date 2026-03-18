"""Core data structures for the 缠论 (Chan Theory) quantitative analysis pipeline.

All dataclasses are frozen (immutable). All financial values use Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ── Enums ────────────────────────────────────────────────────────────────────


class Direction(Enum):
    UP = auto()
    DOWN = auto()


class FractalType(Enum):
    TOP = auto()
    BOTTOM = auto()


class TimeFrame(Enum):
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class SignalType(Enum):
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class TrendClass(Enum):
    UP_TREND = auto()
    DOWN_TREND = auto()
    CONSOLIDATION = auto()


class DivergenceType(Enum):
    TREND = auto()
    CONSOLIDATION = auto()


class SegmentTermType(Enum):
    FIRST_KIND = auto()
    SECOND_KIND = auto()


class MarketRegime(Enum):
    LOW_VOL = auto()
    NORMAL = auto()
    HIGH_VOL = auto()
    EXTREME = auto()


class OutcomeType(Enum):
    CORRECT = auto()
    INCORRECT = auto()
    PARTIAL = auto()
    PENDING = auto()


class EventImpact(Enum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


# ── K-Line Structures ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RawKLine:
    """Original market K-line before containment processing."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    timeframe: TimeFrame = TimeFrame.DAILY


@dataclass(frozen=True)
class StandardKLine:
    """K-line after containment-relationship processing (L0 output)."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    original_count: int = 1
    direction: Direction = Direction.UP
    timeframe: TimeFrame = TimeFrame.DAILY


# ── L1: Fractal ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Fractal:
    """Top or bottom fractal identified from three consecutive StandardKLines."""

    type: FractalType
    timestamp: datetime
    extreme_value: Decimal
    kline_index: int
    elements: tuple[StandardKLine, StandardKLine, StandardKLine]


# ── L2: Stroke (笔) ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Stroke:
    """A stroke (笔) connecting two alternating fractals."""

    direction: Direction
    start_fractal: Fractal
    end_fractal: Fractal
    high: Decimal
    low: Decimal
    kline_count: int
    macd_area: Decimal = Decimal("0")
    macd_dif_start: Decimal = Decimal("0")
    macd_dif_end: Decimal = Decimal("0")
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def duration(self) -> timedelta:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return timedelta(0)

    @property
    def price_range(self) -> Decimal:
        return self.high - self.low


# ── L3: Segment (线段) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Segment:
    """A segment (线段) composed of at least 3 strokes."""

    direction: Direction
    strokes: tuple[Stroke, ...]
    high: Decimal
    low: Decimal
    termination_type: SegmentTermType = SegmentTermType.FIRST_KIND
    macd_area: Decimal = Decimal("0")

    @property
    def start_stroke(self) -> Stroke:
        return self.strokes[0]

    @property
    def end_stroke(self) -> Stroke:
        return self.strokes[-1]

    @property
    def start_time(self) -> datetime | None:
        return self.strokes[0].start_time

    @property
    def end_time(self) -> datetime | None:
        return self.strokes[-1].end_time

    @property
    def duration(self) -> timedelta:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return timedelta(0)

    @property
    def stroke_count(self) -> int:
        return len(self.strokes)


# ── L4: Center (中枢) ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Center:
    """A 中枢 (pivot zone) formed by overlapping segments/strokes."""

    level: TimeFrame
    zg: Decimal  # 中枢上沿
    zd: Decimal  # 中枢下沿
    gg: Decimal  # 波动最高点
    dd: Decimal  # 波动最低点
    segments: tuple[Segment, ...] = ()
    start_time: datetime | None = None
    end_time: datetime | None = None
    extension_count: int = 0


# ── L5: Trend (走势类型) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrendType:
    """Classification of a price movement as trend or consolidation."""

    classification: TrendClass
    centers: tuple[Center, ...]
    level: TimeFrame
    segment_a: Segment | None = None
    center_a: Center | None = None
    segment_b: Segment | None = None
    center_b: Center | None = None
    segment_c: Segment | None = None


# ── L6: Divergence (背驰) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Divergence:
    """Divergence detection result (MACD area comparison a vs c)."""

    type: DivergenceType
    level: TimeFrame
    trend_type: TrendType
    segment_a: Segment
    segment_c: Segment
    a_macd_area: Decimal
    c_macd_area: Decimal
    a_dif_peak: Decimal = Decimal("0")
    c_dif_peak: Decimal = Decimal("0")
    c_contains_b3: bool = False
    volume_ratio: Decimal | None = None
    strength: Decimal = Decimal("0")

    @property
    def area_ratio(self) -> Decimal:
        if self.a_macd_area == Decimal("0"):
            return Decimal("0")
        return Decimal("1") - self.c_macd_area / self.a_macd_area


# ── L7: Signal (买卖点) ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Signal:
    """A buy/sell signal generated by the analysis pipeline."""

    signal_type: SignalType
    level: TimeFrame
    instrument: str
    timestamp: datetime
    price: Decimal
    divergence: Divergence | None = None
    center: Center | None = None
    small_to_large: bool = False
    strength: Decimal = Decimal("0")
    source_lesson: str = ""
    reasoning: str = ""


# ── L8: Interval Nesting (区间套) ────────────────────────────────────────────


@dataclass(frozen=True)
class IntervalNesting:
    """Multi-timeframe interval nesting positioning result."""

    target_level: TimeFrame
    large_signal: Signal | None = None
    medium_signal: Signal | None = None
    precise_signal: Signal | None = None
    nesting_depth: int = 0
    direction_aligned: bool = False
    confidence: Decimal = Decimal("0")


# ── L9: Scan Result ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScanResult:
    """Final scored and ranked result for a single instrument."""

    instrument: str
    signal: Signal
    nesting: IntervalNesting | None = None
    score: Decimal = Decimal("0")
    rank: int = 0
    scan_time: datetime | None = None


# ── L8: Merged Signal (信号去重合并, rule 8.6) ─────────────────────────────────


@dataclass(frozen=True)
class MergedSignal:
    """Combined multi-level signal for one instrument (rule 8.6)."""

    instrument: str
    primary_signal: Signal
    supporting_signals: tuple[Signal, ...] = ()
    nesting_depth: int = 0
    merged_score: Decimal = Decimal("0")
    summary: str = ""


# ── Signal Outcome (信号反馈追踪) ────────────────────────────────────────────


@dataclass(frozen=True)
class SignalOutcome:
    """Post-signal tracking result for feedback and calibration."""

    signal_id: str
    instrument: str
    signal_type: SignalType
    level: TimeFrame
    signal_price: Decimal
    signal_time: datetime
    outcome: OutcomeType = OutcomeType.PENDING
    max_favorable_excursion: Decimal = Decimal("0")
    max_adverse_excursion: Decimal = Decimal("0")
    pnl_at_close: Decimal = Decimal("0")
    bars_to_target: int | None = None
    vix_at_signal: Decimal | None = None
    market_regime: MarketRegime = MarketRegime.NORMAL
    tracking_window: int = 20
    evaluated_at: datetime | None = None


# ── Market Event (事件日历) ──────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketEvent:
    """Market or instrument-level event for signal filtering."""

    event_type: str  # FOMC / CPI / PPI / OPEX / QUAD_WITCHING / EARNINGS
    event_date: date
    instrument: str | None = None  # None = market-wide event
    impact: EventImpact = EventImpact.MEDIUM


# ── MACD Helper ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MACDValue:
    """MACD indicator values for a single K-line."""

    dif: Decimal = Decimal("0")
    dea: Decimal = Decimal("0")
    histogram: Decimal = Decimal("0")


# ── Pipeline State ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineState:
    """Snapshot of the full analysis pipeline state."""

    standard_klines: tuple[StandardKLine, ...] = ()
    fractals: tuple[Fractal, ...] = ()
    strokes: tuple[Stroke, ...] = ()
    segments: tuple[Segment, ...] = ()
    centers: tuple[Center, ...] = ()
    trend: TrendType | None = None
    divergences: tuple[Divergence, ...] = ()
    signals: tuple[Signal, ...] = ()
    nesting: IntervalNesting | None = None
    macd_values: tuple[MACDValue, ...] = ()


# ── Backtest Structures ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Position:
    """A single position in the portfolio."""

    instrument: str
    entry_price: Decimal
    entry_time: datetime
    quantity: Decimal
    direction: Direction
    stop_loss: Decimal | None = None
    trailing_stop: Decimal | None = None
    signal: Signal | None = None
    sector: str = ""  # GICS sector for industry exposure constraint


@dataclass(frozen=True)
class Trade:
    """A completed trade (entry + exit)."""

    instrument: str
    direction: Direction
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    quantity: Decimal
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    signal_type: SignalType | None = None
    exit_reason: str = ""


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Immutable snapshot of portfolio state at a point in time."""

    timestamp: datetime
    cash: Decimal
    positions: tuple[Position, ...] = ()
    trades: tuple[Trade, ...] = ()
    equity: Decimal = Decimal("0")
    drawdown: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")


@dataclass(frozen=True)
class BacktestMetrics:
    """Performance metrics from a backtest run."""

    total_return: Decimal = Decimal("0")
    annualized_return: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    sortino_ratio: Decimal = Decimal("0")
    calmar_ratio: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_duration: timedelta = field(default_factory=timedelta)
    win_rate: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    total_trades: int = 0
    avg_trade_pnl: Decimal = Decimal("0")
    avg_holding_period: timedelta = field(default_factory=timedelta)
