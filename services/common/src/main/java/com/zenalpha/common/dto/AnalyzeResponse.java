package com.zenalpha.common.dto;

import com.zenalpha.common.model.*;

import java.util.List;

public record AnalyzeResponse(
        List<StandardKLine> klines,
        List<Fractal> fractals,
        List<Stroke> strokes,
        List<Segment> segments,
        List<Center> centers,
        List<Signal> signals,
        List<MACDValue> macdValues
) {
    public static AnalyzeResponse from(PipelineState state) {
        return new AnalyzeResponse(
                state.standardKlines(),
                state.fractals(),
                state.strokes(),
                state.segments(),
                state.centers(),
                state.signals(),
                state.macdValues()
        );
    }
}
