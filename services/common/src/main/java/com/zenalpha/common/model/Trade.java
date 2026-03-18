package com.zenalpha.common.model;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.SignalType;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record Trade(
        String instrument,
        Direction direction,
        BigDecimal entryPrice,
        BigDecimal exitPrice,
        LocalDateTime entryTime,
        LocalDateTime exitTime,
        BigDecimal quantity,
        BigDecimal pnl,
        BigDecimal pnlPct,
        SignalType signalType,
        String exitReason
) {
}
