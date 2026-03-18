package com.zenalpha.common.model;

import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record Signal(
        SignalType signalType,
        TimeFrame level,
        String instrument,
        LocalDateTime timestamp,
        BigDecimal price,
        Divergence divergence,
        Center center,
        boolean smallToLarge,
        BigDecimal strength,
        String sourceLesson,
        String reasoning
) {
}
