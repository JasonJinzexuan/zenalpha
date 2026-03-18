package com.zenalpha.common.model;

import com.zenalpha.common.enums.Direction;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;

public record Stroke(
        Direction direction,
        Fractal startFractal,
        Fractal endFractal,
        BigDecimal high,
        BigDecimal low,
        int klineCount,
        BigDecimal macdArea,
        BigDecimal macdDifStart,
        BigDecimal macdDifEnd,
        LocalDateTime startTime,
        LocalDateTime endTime
) {
    public Duration duration() {
        if (startTime != null && endTime != null) {
            return Duration.between(startTime, endTime);
        }
        return Duration.ZERO;
    }

    public BigDecimal priceRange() {
        return high.subtract(low);
    }
}
