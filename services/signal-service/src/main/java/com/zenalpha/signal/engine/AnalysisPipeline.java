package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.*;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Orchestrates L0-L8 into a single analysis pipeline.
 * Feeds raw K-lines through the full 缠论 analysis chain.
 */
@Component
public class AnalysisPipeline {

    private final MACDCalculator macdCalculator;
    private final FractalDetector fractalDetector;
    private final StrokeBuilder strokeBuilder;
    private final SegmentBuilder segmentBuilder;
    private final CenterDetector centerDetector;
    private final TrendClassifier trendClassifier;
    private final DivergenceDetector divergenceDetector;
    private final SignalGenerator signalGenerator;

    public AnalysisPipeline(
            MACDCalculator macdCalculator,
            FractalDetector fractalDetector,
            StrokeBuilder strokeBuilder,
            SegmentBuilder segmentBuilder,
            CenterDetector centerDetector,
            TrendClassifier trendClassifier,
            DivergenceDetector divergenceDetector,
            SignalGenerator signalGenerator) {
        this.macdCalculator = macdCalculator;
        this.fractalDetector = fractalDetector;
        this.strokeBuilder = strokeBuilder;
        this.segmentBuilder = segmentBuilder;
        this.centerDetector = centerDetector;
        this.trendClassifier = trendClassifier;
        this.divergenceDetector = divergenceDetector;
        this.signalGenerator = signalGenerator;
    }

    /**
     * Run the full L0-L8 pipeline on raw K-line data.
     */
    public PipelineState analyze(String instrument, TimeFrame timeframe, List<RawKLine> rawKlines) {
        if (rawKlines == null || rawKlines.isEmpty()) {
            return PipelineState.empty();
        }

        // L0: K-line containment processing
        List<StandardKLine> stdKlines = processKLines(rawKlines);
        if (stdKlines.size() < 3) {
            return new PipelineState(
                    stdKlines, List.of(), List.of(), List.of(), List.of(),
                    null, List.of(), List.of(), null,
                    macdCalculator.compute(stdKlines)
            );
        }

        // L0: MACD calculation
        List<MACDValue> macdValues = macdCalculator.compute(stdKlines);

        // L1: Fractal detection
        List<Fractal> fractals = fractalDetector.detect(stdKlines);

        // L2: Stroke construction
        List<Stroke> strokes = strokeBuilder.build(fractals, macdValues);

        // L3: Segment construction
        List<Segment> segments = segmentBuilder.build(strokes);

        // L4: Center detection
        List<Center> centers = centerDetector.detect(segments, timeframe);

        // L5: Trend classification
        TrendType trend = trendClassifier.classify(centers, segments, timeframe);

        // L6: Divergence detection
        List<Divergence> divergences = divergenceDetector.detect(trend, macdValues);

        // L7: Signal generation
        List<Signal> signals = signalGenerator.generate(
                trend, divergences, centers, segments, strokes, instrument
        );

        return new PipelineState(
                stdKlines,
                fractals,
                strokes,
                segments,
                centers,
                trend,
                divergences,
                signals,
                null,
                macdValues
        );
    }

    private List<StandardKLine> processKLines(List<RawKLine> rawKlines) {
        KLineProcessor processor = new KLineProcessor();
        List<StandardKLine> result = new ArrayList<>();

        for (RawKLine raw : rawKlines) {
            Optional<StandardKLine> std = processor.feed(raw);
            std.ifPresent(result::add);
        }

        // Flush last buffered K-line
        processor.flush().ifPresent(result::add);

        return List.copyOf(result);
    }
}
