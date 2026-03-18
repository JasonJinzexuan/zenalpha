package com.zenalpha.signal.service;

import com.zenalpha.common.model.IntervalNesting;
import com.zenalpha.common.model.ScanResult;
import com.zenalpha.common.model.Signal;
import com.zenalpha.signal.scoring.SignalFilter;
import com.zenalpha.signal.scoring.SignalScorer;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * Scoring + ranking + filtering service.
 */
@Service
public class ScoringService {

    private final SignalScorer scorer;
    private final SignalFilter filter;

    public ScoringService(SignalScorer scorer, SignalFilter filter) {
        this.scorer = scorer;
        this.filter = filter;
    }

    public List<ScanResult> scoreAndFilter(
            List<Signal> signals,
            Map<String, IntervalNesting> nestingMap) {

        List<ScanResult> scored = scorer.scoreBatch(signals, nestingMap);
        return filter.filter(scored);
    }

    public ScanResult scoreSingle(Signal signal, IntervalNesting nesting) {
        return scorer.score(signal, nesting);
    }
}
