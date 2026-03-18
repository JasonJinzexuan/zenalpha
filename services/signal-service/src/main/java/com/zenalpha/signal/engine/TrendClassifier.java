package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.enums.TrendClass;
import com.zenalpha.common.model.Center;
import com.zenalpha.common.model.Segment;
import com.zenalpha.common.model.TrendType;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * L5: Trend classification (趋势与盘整分类).
 * Rules 5.1-5.3 + a+A+b+B+c structure extraction.
 */
@Component
public class TrendClassifier {

    public TrendType classify(List<Center> centers, List<Segment> segments, TimeFrame level) {
        if (centers == null || centers.isEmpty()) {
            return new TrendType(
                    TrendClass.CONSOLIDATION,
                    List.of(),
                    level,
                    null, null, null, null, null
            );
        }

        // Rule 5.1: Single center → consolidation
        if (centers.size() == 1) {
            return classifyConsolidation(centers.getFirst(), segments, level);
        }

        // Rule 5.2: Up trend — ≥2 centers, posterior ZD > anterior ZG (non-overlapping upward)
        if (isUpTrend(centers)) {
            return buildTrend(TrendClass.UP_TREND, centers, segments, level, Direction.UP);
        }

        // Rule 5.3: Down trend — ≥2 centers, posterior ZG < anterior ZD (non-overlapping downward)
        if (isDownTrend(centers)) {
            return buildTrend(TrendClass.DOWN_TREND, centers, segments, level, Direction.DOWN);
        }

        // Default: consolidation with latest center
        return classifyConsolidation(centers.getLast(), segments, level);
    }

    private static boolean isUpTrend(List<Center> centers) {
        for (int i = 0; i < centers.size() - 1; i++) {
            // b's ZD > a's ZG
            if (!(centers.get(i + 1).zd().compareTo(centers.get(i).zg()) > 0)) {
                return false;
            }
        }
        return true;
    }

    private static boolean isDownTrend(List<Center> centers) {
        for (int i = 0; i < centers.size() - 1; i++) {
            // b's ZG < a's ZD
            if (!(centers.get(i + 1).zg().compareTo(centers.get(i).zd()) < 0)) {
                return false;
            }
        }
        return true;
    }

    private static TrendType classifyConsolidation(Center center, List<Segment> segments, TimeFrame level) {
        return new TrendType(
                TrendClass.CONSOLIDATION,
                List.of(center),
                level,
                null, center, null, null, null
        );
    }

    /**
     * Build a+A+b+B+c trend structure.
     * a = entry segment before first center (A)
     * A = penultimate center (centerA)
     * b = connecting segment between A and B
     * B = last center (centerB)
     * c = exit segment after B
     */
    private static TrendType buildTrend(
            TrendClass classification,
            List<Center> centers,
            List<Segment> segments,
            TimeFrame level,
            Direction direction) {

        Center centerA = centers.size() >= 2 ? centers.get(centers.size() - 2) : null;
        Center centerB = centers.getLast();

        Segment segA = centerA != null ? findEntrySegment(segments, centerA, direction) : null;
        Segment segB = centerA != null ? findSegmentBetween(segments, centerA, centerB) : null;
        Segment segC = findExitSegment(segments, centerB, direction);

        return new TrendType(
                classification,
                List.copyOf(centers),
                level,
                segA, centerA, segB, centerB, segC
        );
    }

    private static Segment findEntrySegment(List<Segment> segments, Center center, Direction direction) {
        if (center.startTime() == null) {
            return null;
        }
        for (int i = segments.size() - 1; i >= 0; i--) {
            Segment seg = segments.get(i);
            if (seg.endTime() != null && !seg.endTime().isAfter(center.startTime())) {
                if (seg.direction() == direction) {
                    return seg;
                }
            }
        }
        return null;
    }

    private static Segment findSegmentBetween(List<Segment> segments, Center centerA, Center centerB) {
        if (centerA.endTime() == null || centerB.startTime() == null) {
            return null;
        }
        for (Segment seg : segments) {
            if (seg.startTime() != null && seg.endTime() != null) {
                if (!seg.startTime().isBefore(centerA.endTime())
                        && !seg.endTime().isAfter(centerB.startTime())) {
                    return seg;
                }
            }
        }
        return null;
    }

    private static Segment findExitSegment(List<Segment> segments, Center center, Direction direction) {
        if (center.endTime() == null) {
            return null;
        }
        for (Segment seg : segments) {
            if (seg.startTime() != null && !seg.startTime().isBefore(center.endTime())) {
                if (seg.direction() == direction) {
                    return seg;
                }
            }
        }
        return null;
    }
}
