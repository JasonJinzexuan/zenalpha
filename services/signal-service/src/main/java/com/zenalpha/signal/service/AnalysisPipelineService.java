package com.zenalpha.signal.service;

import com.zenalpha.common.dto.AnalyzeRequest;
import com.zenalpha.common.dto.AnalyzeResponse;
import com.zenalpha.common.model.PipelineState;
import com.zenalpha.signal.engine.AnalysisPipeline;
import org.springframework.stereotype.Service;

/**
 * Service wrapping the AnalysisPipeline for request/response handling.
 */
@Service
public class AnalysisPipelineService {

    private final AnalysisPipeline pipeline;

    public AnalysisPipelineService(AnalysisPipeline pipeline) {
        this.pipeline = pipeline;
    }

    public AnalyzeResponse analyze(AnalyzeRequest request) {
        PipelineState state = pipeline.analyze(
                request.instrument(),
                request.timeframe(),
                request.klines()
        );
        return AnalyzeResponse.from(state);
    }

    public PipelineState analyzeRaw(AnalyzeRequest request) {
        return pipeline.analyze(
                request.instrument(),
                request.timeframe(),
                request.klines()
        );
    }
}
