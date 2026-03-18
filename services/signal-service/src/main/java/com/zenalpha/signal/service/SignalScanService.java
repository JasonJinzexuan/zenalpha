package com.zenalpha.signal.service;

import com.zenalpha.common.dto.ScanRequest;
import com.zenalpha.common.dto.ScanResponse;
import com.zenalpha.common.model.*;
import com.zenalpha.signal.engine.AnalysisPipeline;
import com.zenalpha.signal.engine.IntervalNester;
import com.zenalpha.signal.entity.SignalEntity;
import com.zenalpha.signal.repository.SignalRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.*;

/**
 * Multi-instrument scanning service.
 * Analyzes multiple instruments, scores signals, persists results.
 */
@Service
public class SignalScanService {

    private static final Logger log = LoggerFactory.getLogger(SignalScanService.class);

    private final AnalysisPipeline pipeline;
    private final ScoringService scoringService;
    private final IntervalNester intervalNester;
    private final SignalRepository signalRepository;

    public SignalScanService(
            AnalysisPipeline pipeline,
            ScoringService scoringService,
            IntervalNester intervalNester,
            SignalRepository signalRepository) {
        this.pipeline = pipeline;
        this.scoringService = scoringService;
        this.intervalNester = intervalNester;
        this.signalRepository = signalRepository;
    }

    /**
     * Scan multiple instruments, score and rank signals.
     * Note: In production, kline data would be fetched from data-service.
     * This method accepts pre-fetched data per instrument.
     */
    public ScanResponse scan(ScanRequest request,
                             Map<String, List<RawKLine>> klinesByInstrument) {

        List<Signal> allSignals = new ArrayList<>();
        Map<String, IntervalNesting> nestingMap = new HashMap<>();

        for (String instrument : request.instruments()) {
            List<RawKLine> klines = klinesByInstrument.getOrDefault(instrument, List.of());
            if (klines.isEmpty()) {
                log.warn("No kline data for instrument: {}", instrument);
                continue;
            }

            PipelineState state = pipeline.analyze(instrument, request.timeframe(), klines);
            allSignals.addAll(state.signals());

            // Interval nesting (single-level for now)
            if (!state.signals().isEmpty()) {
                Map<com.zenalpha.common.enums.TimeFrame, List<Signal>> signalsByLevel = new HashMap<>();
                signalsByLevel.put(request.timeframe(), state.signals());
                IntervalNesting nesting = intervalNester.nestFromSignals(signalsByLevel);
                if (nesting != null) {
                    nestingMap.put(instrument, nesting);
                }
            }
        }

        List<ScanResult> results = scoringService.scoreAndFilter(allSignals, nestingMap);

        // Persist signals
        persistSignals(results);

        return new ScanResponse(results);
    }

    private void persistSignals(List<ScanResult> results) {
        for (ScanResult result : results) {
            Signal sig = result.signal();
            BigDecimal divStrength = sig.divergence() != null
                    ? sig.divergence().strength() : null;
            BigDecimal volRatio = sig.divergence() != null
                    ? sig.divergence().volumeRatio() : null;

            SignalEntity entity = SignalEntity.create(
                    sig.instrument(),
                    sig.signalType(),
                    sig.level(),
                    sig.price(),
                    sig.strength(),
                    result.score(),
                    sig.timestamp(),
                    sig.sourceLesson(),
                    sig.reasoning(),
                    divStrength,
                    volRatio,
                    sig.smallToLarge()
            );

            signalRepository.save(entity);
        }
    }
}
