package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.SegmentTermType;
import com.zenalpha.common.model.Segment;
import com.zenalpha.common.model.Stroke;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * L3: Segment construction (线段划分).
 * CRITICAL: implements both FIRST_KIND and SECOND_KIND termination.
 * Rules 3.0-3.5 from algorithm.md.
 */
@Component
public class SegmentBuilder {

    public List<Segment> build(List<Stroke> strokes) {
        if (strokes == null || strokes.size() < 3) {
            return List.of();
        }

        List<Segment> segments = new ArrayList<>();
        List<Stroke> buffer = new ArrayList<>();
        Direction segDirection = strokes.getFirst().direction();

        for (Stroke stroke : strokes) {
            buffer.add(stroke);

            // Rule 3.0: Need at least 3 strokes
            if (buffer.size() < 3) {
                continue;
            }

            // Check first 3 strokes have overlap (segment formation condition)
            if (buffer.size() == 3 && !hasInitialOverlap(buffer)) {
                buffer.remove(0);
                segDirection = buffer.getFirst().direction();
                continue;
            }

            // Try to detect termination
            SegmentTermType termType = tryTerminate(buffer, segDirection);
            if (termType != null) {
                Segment seg = makeSegment(buffer, segDirection, termType);
                segments.add(seg);

                // Last stroke starts new segment
                Stroke last = buffer.getLast();
                buffer.clear();
                buffer.add(last);
                segDirection = last.direction();
            }
        }

        return Collections.unmodifiableList(segments);
    }

    // Rule 3.0: First 3 strokes must have overlap
    private static boolean hasInitialOverlap(List<Stroke> strokes) {
        if (strokes.size() < 3) {
            return false;
        }
        Stroke s1 = strokes.get(0);
        Stroke s2 = strokes.get(1);
        Stroke s3 = strokes.get(2);

        BigDecimal overlapHigh = s1.high().min(s3.high());
        BigDecimal overlapLow = s1.low().max(s3.low());
        return overlapHigh.compareTo(overlapLow) > 0;
    }

    private static SegmentTermType tryTerminate(List<Stroke> strokes, Direction segDirection) {
        List<CharElement> charSeq = buildCharSequence(strokes, segDirection);
        List<CharElement> stdChars = standardizeCharSequence(charSeq, segDirection);

        // Rule 3.3: First-kind termination
        if (checkFirstKind(stdChars, segDirection)) {
            return SegmentTermType.FIRST_KIND;
        }

        // Rule 3.4: Second-kind termination
        if (checkSecondKind(stdChars, strokes, segDirection)) {
            return SegmentTermType.SECOND_KIND;
        }

        return null;
    }

    // --- Characteristic Sequence (特征序列) ---

    // Rule 3.1: Build from counter-direction strokes
    private static List<CharElement> buildCharSequence(List<Stroke> strokes, Direction segDirection) {
        List<CharElement> elements = new ArrayList<>();
        for (int i = 0; i < strokes.size(); i++) {
            Stroke s = strokes.get(i);
            if (s.direction() != segDirection) {
                elements.add(new CharElement(s.high(), s.low(), s, i));
            }
        }
        return elements;
    }

    // Rule 3.2: Containment processing on characteristic sequence
    private static List<CharElement> standardizeCharSequence(List<CharElement> elements, Direction direction) {
        if (elements.size() < 2) {
            return new ArrayList<>(elements);
        }

        List<CharElement> result = new ArrayList<>();
        result.add(elements.getFirst());

        for (int i = 1; i < elements.size(); i++) {
            CharElement last = result.getLast();
            CharElement elem = elements.get(i);

            if (charContainment(last, elem)) {
                CharElement merged = mergeCharElements(last, elem, direction);
                result.set(result.size() - 1, merged);
            } else {
                result.add(elem);
            }
        }
        return result;
    }

    private static boolean charContainment(CharElement a, CharElement b) {
        boolean aContainsB = a.high.compareTo(b.high) >= 0 && a.low.compareTo(b.low) <= 0;
        boolean bContainsA = b.high.compareTo(a.high) >= 0 && b.low.compareTo(a.low) <= 0;
        return aContainsB || bContainsA;
    }

    private static CharElement mergeCharElements(CharElement a, CharElement b, Direction direction) {
        if (direction == Direction.UP) {
            return new CharElement(a.high.max(b.high), a.low.max(b.low), a.stroke, a.index);
        }
        return new CharElement(a.high.min(b.high), a.low.min(b.low), a.stroke, a.index);
    }

    // Rule 3.3: First-kind — fractal in char seq + no gap between elem 1&2
    private static boolean checkFirstKind(List<CharElement> stdChars, Direction segDirection) {
        if (stdChars.size() < 3) {
            return false;
        }

        for (int i = 1; i < stdChars.size() - 1; i++) {
            CharElement a = stdChars.get(i - 1);
            CharElement b = stdChars.get(i);
            CharElement c = stdChars.get(i + 1);

            boolean hasFractal;
            if (segDirection == Direction.UP) {
                hasFractal = hasCharTopFractal(a, b, c);
            } else {
                hasFractal = hasCharBottomFractal(a, b, c);
            }

            if (hasFractal && !hasGap(stdChars.get(0), stdChars.get(1), segDirection)) {
                return true;
            }
        }
        return false;
    }

    // Rule 3.4: Second-kind — gap between elem 1&2 + reverse seq has fractal
    private static boolean checkSecondKind(
            List<CharElement> stdChars, List<Stroke> strokes, Direction segDirection) {

        if (stdChars.size() < 2) {
            return false;
        }

        // Must have gap between first two elements
        if (!hasGap(stdChars.get(0), stdChars.get(1), segDirection)) {
            return false;
        }

        // Build reverse characteristic sequence (same-direction strokes)
        Direction reverseDir = segDirection == Direction.UP ? Direction.DOWN : Direction.UP;
        List<CharElement> reverseElements = buildCharSequence(strokes, reverseDir);
        List<CharElement> reverseStd = standardizeCharSequence(reverseElements, reverseDir);

        if (reverseStd.size() < 3) {
            return false;
        }

        for (int i = 1; i < reverseStd.size() - 1; i++) {
            CharElement a = reverseStd.get(i - 1);
            CharElement b = reverseStd.get(i);
            CharElement c = reverseStd.get(i + 1);

            if (reverseDir == Direction.UP) {
                if (hasCharBottomFractal(a, b, c)) {
                    return true;
                }
            } else {
                if (hasCharTopFractal(a, b, c)) {
                    return true;
                }
            }
        }
        return false;
    }

    // Rule 3.5: Gap detection
    private static boolean hasGap(CharElement elem1, CharElement elem2, Direction direction) {
        if (direction == Direction.UP) {
            return elem1.low.compareTo(elem2.high) > 0;
        }
        return elem1.high.compareTo(elem2.low) < 0;
    }

    private static boolean hasCharTopFractal(CharElement a, CharElement b, CharElement c) {
        return b.high.compareTo(a.high) > 0 && b.high.compareTo(c.high) > 0;
    }

    private static boolean hasCharBottomFractal(CharElement a, CharElement b, CharElement c) {
        return b.low.compareTo(a.low) < 0 && b.low.compareTo(c.low) < 0;
    }

    private static Segment makeSegment(List<Stroke> strokes, Direction direction, SegmentTermType termType) {
        List<Stroke> strokeList = List.copyOf(strokes);
        BigDecimal high = strokes.stream()
                .map(Stroke::high)
                .reduce(BigDecimal::max)
                .orElse(BigDecimal.ZERO);
        BigDecimal low = strokes.stream()
                .map(Stroke::low)
                .reduce(BigDecimal::min)
                .orElse(BigDecimal.ZERO);
        BigDecimal macdArea = strokes.stream()
                .map(s -> s.macdArea().abs())
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        return new Segment(direction, strokeList, high, low, termType, macdArea);
    }

    // Internal characteristic sequence element
    private record CharElement(BigDecimal high, BigDecimal low, Stroke stroke, int index) {
    }
}
