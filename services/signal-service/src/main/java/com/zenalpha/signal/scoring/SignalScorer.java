package com.zenalpha.signal.scoring;

import com.zenalpha.common.enums.DivergenceType;
import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.IntervalNesting;
import com.zenalpha.common.model.ScanResult;
import com.zenalpha.common.model.Signal;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.IntStream;

/**
 * L9: Signal scoring engine.
 * Score = signal_type × timeframe × divergence_strength × trend_alignment × volume_factor.
 */
@Component
public class SignalScorer {

    private static final int SCALE = 6;

    private static final Map<SignalType, BigDecimal> SIGNAL_TYPE_SCORES = Map.of(
            SignalType.B1, new BigDecimal("5"),
            SignalType.B2, new BigDecimal("4"),
            SignalType.B3, new BigDecimal("5"),
            SignalType.S1, new BigDecimal("5"),
            SignalType.S2, new BigDecimal("4"),
            SignalType.S3, new BigDecimal("5")
    );

    private static final Map<TimeFrame, BigDecimal> TIMEFRAME_WEIGHTS = Map.of(
            TimeFrame.MONTHLY, new BigDecimal("8"),
            TimeFrame.WEEKLY, new BigDecimal("5"),
            TimeFrame.DAILY, new BigDecimal("3"),
            TimeFrame.HOUR_1, new BigDecimal("2"),
            TimeFrame.MIN_30, new BigDecimal("2"),
            TimeFrame.MIN_5, BigDecimal.ONE,
            TimeFrame.MIN_1, BigDecimal.ONE
    );

    public ScanResult score(Signal signal, IntervalNesting nesting) {
        BigDecimal signalScore = SIGNAL_TYPE_SCORES.getOrDefault(signal.signalType(), BigDecimal.ONE);
        BigDecimal timeframeWeight = TIMEFRAME_WEIGHTS.getOrDefault(signal.level(), BigDecimal.ONE);
        BigDecimal divStrength = divergenceStrength(signal);
        BigDecimal trendAlign = trendAlignment(signal, nesting);
        BigDecimal volFactor = volumeFactor(signal);

        BigDecimal composite = signalScore
                .multiply(timeframeWeight)
                .multiply(divStrength)
                .multiply(trendAlign)
                .multiply(volFactor)
                .setScale(SCALE, RoundingMode.HALF_UP);

        return new ScanResult(
                signal.instrument(),
                signal,
                nesting,
                composite,
                0,
                LocalDateTime.now()
        );
    }

    public List<ScanResult> scoreBatch(List<Signal> signals, Map<String, IntervalNesting> nestingMap) {
        List<ScanResult> results = new ArrayList<>();
        for (Signal sig : signals) {
            IntervalNesting nesting = nestingMap != null ? nestingMap.get(sig.instrument()) : null;
            results.add(score(sig, nesting));
        }

        // Sort by score descending
        results.sort(Comparator.comparing(ScanResult::score).reversed());

        // Assign ranks
        return IntStream.range(0, results.size())
                .mapToObj(i -> {
                    ScanResult r = results.get(i);
                    return new ScanResult(
                            r.instrument(), r.signal(), r.nesting(),
                            r.score(), i + 1, r.scanTime()
                    );
                })
                .toList();
    }

    private static BigDecimal divergenceStrength(Signal signal) {
        if (signal.divergence() == null) {
            return new BigDecimal("0.5");
        }
        BigDecimal aArea = signal.divergence().aMacdArea().abs();
        BigDecimal cArea = signal.divergence().cMacdArea().abs();
        if (aArea.compareTo(BigDecimal.ZERO) == 0) {
            return new BigDecimal("0.5");
        }
        BigDecimal strength = BigDecimal.ONE.subtract(
                cArea.divide(aArea, SCALE, RoundingMode.HALF_UP));
        return strength.max(BigDecimal.ZERO).min(BigDecimal.ONE);
    }

    private static BigDecimal trendAlignment(Signal signal, IntervalNesting nesting) {
        if (nesting == null) {
            return new BigDecimal("2");
        }
        if (nesting.directionAligned()) {
            return new BigDecimal("3");
        }
        if (nesting.nestingDepth() >= 2) {
            return new BigDecimal("2");
        }
        return BigDecimal.ONE;
    }

    private static BigDecimal volumeFactor(Signal signal) {
        if (signal.divergence() == null) {
            return BigDecimal.ONE;
        }
        BigDecimal volRatio = signal.divergence().volumeRatio();
        if (volRatio == null) {
            return BigDecimal.ONE;
        }
        if (signal.divergence().type() == DivergenceType.TREND) {
            if (volRatio.compareTo(new BigDecimal("0.7")) < 0) {
                return new BigDecimal("1.3");
            }
            if (volRatio.compareTo(new BigDecimal("1.3")) > 0) {
                return new BigDecimal("0.7");
            }
            return BigDecimal.ONE;
        }
        // Consolidation divergence
        if (volRatio.compareTo(new BigDecimal("1.5")) > 0) {
            return new BigDecimal("1.5");
        }
        if (volRatio.compareTo(new BigDecimal("0.5")) < 0) {
            return new BigDecimal("0.5");
        }
        return BigDecimal.ONE;
    }
}
