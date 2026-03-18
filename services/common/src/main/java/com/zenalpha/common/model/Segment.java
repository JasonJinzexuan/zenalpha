package com.zenalpha.common.model;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.SegmentTermType;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

public record Segment(
        Direction direction,
        List<Stroke> strokes,
        BigDecimal high,
        BigDecimal low,
        SegmentTermType terminationType,
        BigDecimal macdArea
) {
    public Stroke startStroke() {
        return strokes.getFirst();
    }

    public Stroke endStroke() {
        return strokes.getLast();
    }

    public LocalDateTime startTime() {
        return startStroke().startTime();
    }

    public LocalDateTime endTime() {
        return endStroke().endTime();
    }

    public Duration duration() {
        LocalDateTime start = startTime();
        LocalDateTime end = endTime();
        if (start != null && end != null) {
            return Duration.between(start, end);
        }
        return Duration.ZERO;
    }

    public int strokeCount() {
        return strokes.size();
    }
}
