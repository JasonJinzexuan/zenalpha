package com.zenalpha.common.model;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record ScanResult(
        String instrument,
        Signal signal,
        IntervalNesting nesting,
        BigDecimal score,
        int rank,
        LocalDateTime scanTime
) {
}
