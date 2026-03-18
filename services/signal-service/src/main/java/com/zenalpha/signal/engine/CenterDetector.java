package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.Center;
import com.zenalpha.common.model.Segment;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * L4: Center identification (中枢识别).
 * Rules 4.1-4.4: formation, extension, new birth, expansion.
 */
@Component
public class CenterDetector {

    public List<Center> detect(List<Segment> segments, TimeFrame level) {
        if (segments == null || segments.size() < 3) {
            return List.of();
        }

        List<Center> completed = new ArrayList<>();
        List<Segment> buffer = new ArrayList<>();
        Center current = null;

        for (Segment segment : segments) {
            if (current != null) {
                // Rule 4.2: Extension — segment overlaps [ZD, ZG]
                if (segmentOverlapsRange(segment, current.zd(), current.zg())) {
                    current = extendCenter(current, segment);
                    continue;
                }

                // Rule 4.3: New birth — segment leaves [ZD, ZG]
                // Current center is complete
                Center toAdd = current;

                // Rule 4.4: Expansion — check if previous completed center overlaps [DD, GG]
                if (!completed.isEmpty()) {
                    Center expanded = expandCenters(completed.getLast(), toAdd);
                    if (expanded != null) {
                        completed.set(completed.size() - 1, expanded);
                        toAdd = null;
                    }
                }
                if (toAdd != null) {
                    completed.add(toAdd);
                }

                current = null;
                buffer.clear();
                buffer.add(segment);
                continue;
            }

            // Accumulate segments for initial formation
            buffer.add(segment);
            if (buffer.size() < 3) {
                continue;
            }

            current = tryFormCenter(buffer, level);
            if (current != null) {
                buffer.clear();
            } else {
                buffer.remove(0);
            }
        }

        // Don't forget the active center
        if (current != null) {
            completed.add(current);
        }

        return Collections.unmodifiableList(completed);
    }

    // Rule 4.1: Three segments with overlapping range
    private static Center tryFormCenter(List<Segment> buffer, TimeFrame level) {
        if (buffer.size() < 3) {
            return null;
        }

        // Check overlap between first two segments
        BigDecimal zg = buffer.get(0).high().min(buffer.get(1).high());
        BigDecimal zd = buffer.get(0).low().max(buffer.get(1).low());

        if (zg.compareTo(zd) <= 0) {
            return null;
        }

        // Check if third segment overlaps
        if (!segmentOverlapsRange(buffer.get(2), zd, zg)) {
            return null;
        }

        return makeCenter(new ArrayList<>(buffer.subList(0, 3)), zg, zd, level);
    }

    private static boolean segmentOverlapsRange(Segment seg, BigDecimal zd, BigDecimal zg) {
        return seg.high().compareTo(zd) > 0 && seg.low().compareTo(zg) < 0;
    }

    // Rule 4.2
    private static Center extendCenter(Center center, Segment segment) {
        List<Segment> newSegments = new ArrayList<>(center.segments());
        newSegments.add(segment);
        BigDecimal newGg = center.gg().max(segment.high());
        BigDecimal newDd = center.dd().min(segment.low());

        return new Center(
                center.level(),
                center.zg(),
                center.zd(),
                newGg,
                newDd,
                List.copyOf(newSegments),
                center.startTime(),
                segment.endTime(),
                center.extensionCount() + 1
        );
    }

    // Rule 4.4: Two same-level centers with overlapping [DD,GG] ranges merge
    private static Center expandCenters(Center a, Center b) {
        if (a.level() != b.level()) {
            return null;
        }
        // Check [DD, GG] overlap
        if (!(a.gg().compareTo(b.dd()) > 0 && b.gg().compareTo(a.dd()) > 0)) {
            return null;
        }

        List<Segment> allSegments = new ArrayList<>(a.segments());
        allSegments.addAll(b.segments());

        BigDecimal newZg = a.zg().min(b.zg());
        BigDecimal newZd = a.zd().max(b.zd());

        if (newZg.compareTo(newZd) <= 0) {
            // Expanded range invalid — use wider bounds
            newZg = a.zg().max(b.zg());
            newZd = a.zd().min(b.zd());
        }

        return makeCenter(allSegments, newZg, newZd, a.level());
    }

    private static Center makeCenter(List<Segment> segments, BigDecimal zg, BigDecimal zd, TimeFrame level) {
        BigDecimal gg = segments.stream().map(Segment::high).reduce(BigDecimal::max).orElse(BigDecimal.ZERO);
        BigDecimal dd = segments.stream().map(Segment::low).reduce(BigDecimal::min).orElse(BigDecimal.ZERO);

        return new Center(
                level,
                zg,
                zd,
                gg,
                dd,
                List.copyOf(segments),
                segments.getFirst().startTime(),
                segments.getLast().endTime(),
                Math.max(0, segments.size() - 3)
        );
    }
}
