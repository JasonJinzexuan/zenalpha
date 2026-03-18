package com.zenalpha.common.model;

import com.zenalpha.common.enums.TimeFrame;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record Center(
        TimeFrame level,
        BigDecimal zg,
        BigDecimal zd,
        BigDecimal gg,
        BigDecimal dd,
        List<Segment> segments,
        LocalDateTime startTime,
        LocalDateTime endTime,
        int extensionCount
) {
    public BigDecimal range() {
        return zg.subtract(zd);
    }

    public BigDecimal midPoint() {
        return zg.add(zd).divide(BigDecimal.valueOf(2), zg.scale(), java.math.RoundingMode.HALF_UP);
    }
}
