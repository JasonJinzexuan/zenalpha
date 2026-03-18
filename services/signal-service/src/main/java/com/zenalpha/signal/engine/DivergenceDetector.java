package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.DivergenceType;
import com.zenalpha.common.enums.TrendClass;
import com.zenalpha.common.model.*;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * L6: Divergence detection (背驰判断).
 * [Correction 1]: Compares a vs c (NOT b vs c).
 * [Correction 2]: c segment MUST contain B3 for trend divergence.
 * Rules 6.1-6.4.
 */
@Component
public class DivergenceDetector {

    private static final BigDecimal NEAR_ZERO_THRESHOLD = new BigDecimal("0.05");
    private static final BigDecimal STAGNATION_RATIO = new BigDecimal("0.8");
    private static final BigDecimal VOLUME_LOW = new BigDecimal("0.7");
    private static final BigDecimal VOLUME_HIGH = new BigDecimal("1.3");
    private static final int SCALE = 6;

    public List<Divergence> detect(TrendType trend, List<MACDValue> macdValues) {
        if (trend == null) {
            return List.of();
        }

        List<Divergence> result = new ArrayList<>();

        if (trend.classification() == TrendClass.UP_TREND
                || trend.classification() == TrendClass.DOWN_TREND) {
            Divergence trendDiv = detectTrendDivergence(trend, macdValues);
            if (trendDiv != null) {
                result.add(trendDiv);
            }
        }

        if (trend.classification() == TrendClass.CONSOLIDATION) {
            Divergence consolDiv = detectConsolidationDivergence(trend, macdValues);
            if (consolDiv != null) {
                result.add(consolDiv);
            }
        }

        return List.copyOf(result);
    }

    // Rule 6.1: Trend divergence — a vs c comparison
    private Divergence detectTrendDivergence(TrendType trend, List<MACDValue> macdValues) {
        Segment segA = trend.segmentA();
        Segment segC = trend.segmentC();
        if (segA == null || segC == null) {
            return null;
        }

        BigDecimal aArea = segmentMacdArea(segA);
        BigDecimal cArea = segmentMacdArea(segC);
        BigDecimal aDif = segmentDifPeak(segA);
        BigDecimal cDif = segmentDifPeak(segC);

        // Rule 6.3: Need at least 2 of 3 confirmations
        int confirmations = countConfirmations(aArea, cArea, aDif, cDif);
        if (confirmations < 2) {
            return null;
        }

        // Rule 6.1: MACD histogram returns near zero at center B
        if (!macdReturnsNearZero(macdValues, trend.centerB())) {
            return null;
        }

        // [Correction 2]: c must contain B3
        boolean containsB3 = segmentCContainsB3(segC, trend.centerB());

        BigDecimal strength = calcStrength(aArea, cArea);

        // Rule 6.4: Volume ratio
        BigDecimal volumeRatio = calcVolumeRatio(segA, segC);

        return new Divergence(
                DivergenceType.TREND,
                trend.level(),
                trend,
                segA,
                segC,
                aArea,
                cArea,
                aDif,
                cDif,
                containsB3,
                volumeRatio,
                strength
        );
    }

    // Rule 6.2: Consolidation divergence — same-direction exit segments
    private Divergence detectConsolidationDivergence(TrendType trend, List<MACDValue> macdValues) {
        Center center = trend.centerA();
        if (center == null) {
            return null;
        }

        // Find segments after the center, same direction
        List<Segment> centerSegments = center.segments();
        if (centerSegments.size() < 2) {
            return null;
        }

        // Use first and last segment of the center as exit comparison
        Segment segA = centerSegments.get(0);
        Segment segC = centerSegments.get(centerSegments.size() - 1);

        if (segA.direction() != segC.direction()) {
            return null;
        }

        BigDecimal aArea = segmentMacdArea(segA);
        BigDecimal cArea = segmentMacdArea(segC);
        BigDecimal aDif = segmentDifPeak(segA);
        BigDecimal cDif = segmentDifPeak(segC);

        int confirmations = countConfirmations(aArea, cArea, aDif, cDif);
        if (confirmations < 2) {
            return null;
        }

        BigDecimal strength = calcStrength(aArea, cArea);

        return new Divergence(
                DivergenceType.CONSOLIDATION,
                trend.level(),
                trend,
                segA,
                segC,
                aArea,
                cArea,
                aDif,
                cDif,
                false,
                null,
                strength
        );
    }

    // MACD area for a segment
    private static BigDecimal segmentMacdArea(Segment segment) {
        if (segment.macdArea().compareTo(BigDecimal.ZERO) != 0) {
            return segment.macdArea().abs();
        }
        BigDecimal total = BigDecimal.ZERO;
        for (Stroke stroke : segment.strokes()) {
            total = total.add(stroke.macdArea().abs());
        }
        return total;
    }

    // Peak DIF within segment strokes
    private static BigDecimal segmentDifPeak(Segment segment) {
        BigDecimal peak = BigDecimal.ZERO;
        for (Stroke stroke : segment.strokes()) {
            BigDecimal candidate = stroke.macdDifStart().abs().max(stroke.macdDifEnd().abs());
            if (candidate.compareTo(peak) > 0) {
                peak = candidate;
            }
        }
        return peak;
    }

    // Rule 6.3: Multi-confirmation (need ≥ 2 of 3)
    private static int countConfirmations(
            BigDecimal aArea, BigDecimal cArea,
            BigDecimal aDif, BigDecimal cDif) {

        int count = 0;
        // 1. MACD area shrinks
        if (cArea.compareTo(aArea) < 0 && aArea.compareTo(BigDecimal.ZERO) > 0) {
            count++;
        }
        // 2. DIF does not make new extreme
        if (cDif.compareTo(aDif) < 0 && aDif.compareTo(BigDecimal.ZERO) > 0) {
            count++;
        }
        // 3. Stagnation — c area is small relative to a
        if (aArea.compareTo(BigDecimal.ZERO) > 0) {
            BigDecimal ratio = cArea.divide(aArea, SCALE, RoundingMode.HALF_UP);
            if (ratio.compareTo(STAGNATION_RATIO) < 0) {
                count++;
            }
        }
        return count;
    }

    // MACD returns near zero at center B
    private static boolean macdReturnsNearZero(List<MACDValue> macdValues, Center centerB) {
        if (centerB == null || macdValues == null || macdValues.isEmpty()) {
            return false;
        }
        for (MACDValue val : macdValues) {
            if (val.histogram().abs().compareTo(NEAR_ZERO_THRESHOLD) < 0) {
                return true;
            }
        }
        return false;
    }

    // [Correction 2]: c must contain B3 structure (break above ZG / below ZD and pullback)
    private static boolean segmentCContainsB3(Segment segC, Center centerB) {
        if (centerB == null) {
            return false;
        }
        for (Stroke stroke : segC.strokes()) {
            // Break above ZG and stays above
            if (stroke.high().compareTo(centerB.zg()) > 0
                    && stroke.low().compareTo(centerB.zg()) >= 0) {
                return true;
            }
            // Break below ZD and stays below
            if (stroke.low().compareTo(centerB.zd()) < 0
                    && stroke.high().compareTo(centerB.zd()) <= 0) {
                return true;
            }
        }
        return false;
    }

    // Rule 6.4: Volume ratio
    private static BigDecimal calcVolumeRatio(Segment segA, Segment segC) {
        long volA = 0;
        for (Stroke s : segA.strokes()) {
            if (!s.startFractal().elements().isEmpty()) {
                volA += s.startFractal().elements().get(0).volume();
            }
        }
        long volC = 0;
        for (Stroke s : segC.strokes()) {
            if (!s.startFractal().elements().isEmpty()) {
                volC += s.startFractal().elements().get(0).volume();
            }
        }
        if (volA == 0) {
            return null;
        }
        return BigDecimal.valueOf(volC).divide(BigDecimal.valueOf(volA), SCALE, RoundingMode.HALF_UP);
    }

    // strength = 1 - c_area / a_area
    private static BigDecimal calcStrength(BigDecimal aArea, BigDecimal cArea) {
        if (aArea.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }
        return BigDecimal.ONE.subtract(cArea.divide(aArea, SCALE, RoundingMode.HALF_UP));
    }
}
