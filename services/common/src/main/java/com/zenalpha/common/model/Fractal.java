package com.zenalpha.common.model;

import com.zenalpha.common.enums.FractalType;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record Fractal(
        FractalType type,
        LocalDateTime timestamp,
        BigDecimal extremeValue,
        int klineIndex,
        List<StandardKLine> elements
) {
}
