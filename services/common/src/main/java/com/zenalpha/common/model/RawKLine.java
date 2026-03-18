package com.zenalpha.common.model;

import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record RawKLine(
        LocalDateTime timestamp,
        BigDecimal open,
        BigDecimal high,
        BigDecimal low,
        BigDecimal close,
        long volume,
        TimeFrame timeframe
) {
    public RawKLine {
        if (high.compareTo(low) < 0) {
            throw new IllegalArgumentException("high must be >= low");
        }
    }
}
