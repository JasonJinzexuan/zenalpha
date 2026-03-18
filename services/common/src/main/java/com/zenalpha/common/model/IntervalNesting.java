package com.zenalpha.common.model;

import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;

public record IntervalNesting(
        TimeFrame targetLevel,
        Signal largeSignal,
        Signal mediumSignal,
        Signal preciseSignal,
        int nestingDepth,
        boolean directionAligned,
        BigDecimal confidence
) {
}
