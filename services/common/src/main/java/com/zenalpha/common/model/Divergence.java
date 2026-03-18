package com.zenalpha.common.model;

import com.zenalpha.common.enums.DivergenceType;
import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;
import java.math.RoundingMode;

public record Divergence(
        DivergenceType type,
        TimeFrame level,
        TrendType trendType,
        Segment segmentA,
        Segment segmentC,
        BigDecimal aMacdArea,
        BigDecimal cMacdArea,
        BigDecimal aDifPeak,
        BigDecimal cDifPeak,
        boolean cContainsB3,
        BigDecimal volumeRatio,
        BigDecimal strength
) {
    public BigDecimal areaRatio() {
        if (aMacdArea.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return BigDecimal.ONE.subtract(cMacdArea.divide(aMacdArea, 6, RoundingMode.HALF_UP));
    }
}
