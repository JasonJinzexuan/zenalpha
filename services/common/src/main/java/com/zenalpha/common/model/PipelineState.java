package com.zenalpha.common.model;

import java.util.List;

public record PipelineState(
        List<StandardKLine> standardKlines,
        List<Fractal> fractals,
        List<Stroke> strokes,
        List<Segment> segments,
        List<Center> centers,
        TrendType trend,
        List<Divergence> divergences,
        List<Signal> signals,
        IntervalNesting nesting,
        List<MACDValue> macdValues
) {
    public static PipelineState empty() {
        return new PipelineState(
                List.of(), List.of(), List.of(), List.of(), List.of(),
                null, List.of(), List.of(), null, List.of()
        );
    }
}
