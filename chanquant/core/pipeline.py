"""Analysis pipeline wiring L0-L8 together.

Feeds raw K-lines through the full 缠论 analysis chain.
"""

from __future__ import annotations

from decimal import Decimal

from chanquant.core.center import CenterDetector
from chanquant.core.divergence import DivergenceDetector
from chanquant.core.fractal import FractalDetector
from chanquant.core.kline import KLineProcessor
from chanquant.core.macd import IncrementalMACD
from chanquant.core.nesting import IntervalNester
from chanquant.core.objects import (
    Center,
    Divergence,
    Fractal,
    MACDValue,
    PipelineState,
    RawKLine,
    Segment,
    Signal,
    StandardKLine,
    Stroke,
    TimeFrame,
    TrendType,
)
from chanquant.core.segment import SegmentBuilder
from chanquant.core.signal import SignalGenerator
from chanquant.core.stroke import StrokeBuilder, attach_macd_area
from chanquant.core.trend import TrendClassifier


class AnalysisPipeline:
    """Wires L0-L8 processors into a single feed-based pipeline."""

    def __init__(
        self,
        level: TimeFrame = TimeFrame.DAILY,
        instrument: str = "",
    ) -> None:
        self._level = level
        self._instrument = instrument

        # Processors
        self._kline_proc = KLineProcessor()
        self._macd = IncrementalMACD()
        self._fractal_det = FractalDetector()
        self._stroke_builder = StrokeBuilder()
        self._segment_builder = SegmentBuilder()
        self._center_det = CenterDetector(level=level)
        self._trend_cls = TrendClassifier()
        self._div_det = DivergenceDetector()
        self._signal_gen = SignalGenerator()
        self._nester = IntervalNester()

        # Accumulated state
        self._klines: list[StandardKLine] = []
        self._macd_values: list[MACDValue] = []
        self._fractals: list[Fractal] = []
        self._strokes: list[Stroke] = []
        self._segments: list[Segment] = []
        self._centers: list[Center] = []
        self._signals: list[Signal] = []
        self._divergences: list[Divergence] = []
        self._trend: TrendType | None = None
        self._kline_index = 0

    def feed(self, raw: RawKLine) -> PipelineState:
        """Feed a raw K-line through the full pipeline."""
        # L0: MACD (calculated on every raw kline)
        macd_val = self._macd.feed(raw.close)
        self._macd_values.append(macd_val)

        # L0: Containment processing
        std_kline = self._kline_proc.feed(raw)
        if std_kline is not None:
            self._process_standard_kline(std_kline)

        return self._snapshot()

    def _process_standard_kline(self, kline: StandardKLine) -> None:
        """Process a finalized standard K-line through L1-L8."""
        self._klines.append(kline)
        self._kline_index += 1

        # L1: Fractal detection
        fractal = self._fractal_det.feed(kline)
        if fractal is None:
            return
        self._fractals.append(fractal)

        # L2: Stroke building
        stroke = self._stroke_builder.feed(fractal)
        if stroke is None:
            return

        # Attach MACD data to stroke
        start_idx = stroke.start_fractal.kline_index
        end_idx = stroke.end_fractal.kline_index
        stroke = attach_macd_area(stroke, self._macd_values, start_idx, end_idx)
        self._strokes.append(stroke)

        # L3: Segment building
        segment = self._segment_builder.feed(stroke)
        if segment is None:
            return
        self._segments.append(segment)

        # L4: Center detection
        center = self._center_det.feed(segment)
        if center is not None:
            self._centers.append(center)

        # L5: Trend classification
        self._trend = self._trend_cls.classify(
            self._centers, self._segments, self._level
        )

        # L6: Divergence detection
        if self._trend is not None:
            div = self._div_det.detect(
                self._trend, self._macd_values, self._segments
            )
            if div is not None:
                self._divergences.append(div)

        # L7: Signal generation
        if self._trend is not None:
            new_signals = self._signal_gen.generate(
                trend=self._trend,
                divergence=self._divergences[-1] if self._divergences else None,
                centers=self._centers,
                segments=self._segments,
                strokes=self._strokes,
                instrument=self._instrument,
            )
            self._signals.extend(new_signals)

    def _snapshot(self) -> PipelineState:
        """Create an immutable snapshot of current state."""
        return PipelineState(
            standard_klines=tuple(self._klines),
            fractals=tuple(self._fractals),
            strokes=tuple(self._strokes),
            segments=tuple(self._segments),
            centers=tuple(self._centers),
            trend=self._trend,
            divergences=tuple(self._divergences),
            signals=tuple(self._signals),
            macd_values=tuple(self._macd_values),
        )
