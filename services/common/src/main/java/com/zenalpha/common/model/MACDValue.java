package com.zenalpha.common.model;

import java.math.BigDecimal;

public record MACDValue(
        BigDecimal dif,
        BigDecimal dea,
        BigDecimal histogram
) {
    public static final MACDValue ZERO = new MACDValue(BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO);
}
