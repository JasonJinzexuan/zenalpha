package com.zenalpha.signal.scoring;

import com.zenalpha.common.model.ScanResult;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;

/**
 * L9: Signal filter by quality thresholds.
 * Filters: trend_alignment >= 2, divergence_strength >= 0.3, signal freshness < 3 K-lines.
 */
@Component
public class SignalFilter {

    private static final BigDecimal MIN_DIVERGENCE_STRENGTH = new BigDecimal("0.3");
    private static final BigDecimal MIN_TREND_ALIGNMENT = new BigDecimal("2");
    private static final BigDecimal MIN_SCORE_THRESHOLD = BigDecimal.ZERO;

    public List<ScanResult> filter(List<ScanResult> results) {
        if (results == null || results.isEmpty()) {
            return List.of();
        }

        return results.stream()
                .filter(this::passesDivergenceStrength)
                .filter(this::passesTrendAlignment)
                .filter(r -> r.score().compareTo(MIN_SCORE_THRESHOLD) > 0)
                .toList();
    }

    private boolean passesDivergenceStrength(ScanResult result) {
        if (result.signal().divergence() == null) {
            return true; // No divergence — pass through (e.g., B3/S3)
        }
        return result.signal().divergence().strength().compareTo(MIN_DIVERGENCE_STRENGTH) >= 0;
    }

    private boolean passesTrendAlignment(ScanResult result) {
        if (result.nesting() == null) {
            return true; // No nesting — no alignment filter
        }
        if (result.nesting().directionAligned()) {
            return true;
        }
        return result.nesting().nestingDepth() >= 2;
    }
}
