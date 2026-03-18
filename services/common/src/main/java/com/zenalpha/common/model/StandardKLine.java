package com.zenalpha.common.model;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record StandardKLine(
        LocalDateTime timestamp,
        BigDecimal open,
        BigDecimal high,
        BigDecimal low,
        BigDecimal close,
        long volume,
        int originalCount,
        Direction direction,
        TimeFrame timeframe
) {
    public StandardKLine {
        if (originalCount < 1) {
            originalCount = 1;
        }
        if (direction == null) {
            direction = Direction.UP;
        }
        if (timeframe == null) {
            timeframe = TimeFrame.DAILY;
        }
    }

    public static StandardKLine fromRaw(RawKLine raw) {
        return new StandardKLine(
                raw.timestamp(), raw.open(), raw.high(), raw.low(), raw.close(),
                raw.volume(), 1, Direction.UP, raw.timeframe()
        );
    }
}
