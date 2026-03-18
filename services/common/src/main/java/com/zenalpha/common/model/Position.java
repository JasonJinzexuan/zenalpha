package com.zenalpha.common.model;

import com.zenalpha.common.enums.Direction;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record Position(
        String instrument,
        BigDecimal entryPrice,
        LocalDateTime entryTime,
        BigDecimal quantity,
        Direction direction,
        BigDecimal stopLoss,
        BigDecimal trailingStop,
        Signal signal
) {
}
