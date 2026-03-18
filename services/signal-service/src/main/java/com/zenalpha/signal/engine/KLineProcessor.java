package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.model.RawKLine;
import com.zenalpha.common.model.StandardKLine;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.Optional;

/**
 * L0: K-line containment processing (包含关系处理).
 * Rules 0.1-0.4 from algorithm.md.
 */
@Component
public class KLineProcessor {

    private StandardKLine prev;
    private StandardKLine current;
    private Direction direction = Direction.UP;
    private int index = 0;

    public void reset() {
        prev = null;
        current = null;
        direction = Direction.UP;
        index = 0;
    }

    /**
     * Feed a raw K-line. Returns a finalized StandardKLine when containment is resolved.
     */
    public Optional<StandardKLine> feed(RawKLine raw) {
        StandardKLine incoming = StandardKLine.fromRaw(raw);

        // First K-line
        if (current == null) {
            current = incoming;
            return Optional.empty();
        }

        // Rule 0.1: Check containment
        if (hasContainment(current, incoming)) {
            // Rule 0.2: Determine merge direction
            if (prev != null) {
                direction = determineDirection(prev, current);
            }
            // Rule 0.3 + 0.4: Merge and continue (recursive containment)
            current = merge(current, incoming, direction);
            return Optional.empty();
        }

        // No containment — finalize current, advance
        StandardKLine finalized = current;
        if (prev != null) {
            direction = determineDirection(prev, finalized);
        }

        prev = finalized;
        current = incoming;
        index++;
        return Optional.of(finalized);
    }

    /**
     * Flush the last buffered K-line.
     */
    public Optional<StandardKLine> flush() {
        if (current != null) {
            StandardKLine result = current;
            current = null;
            return Optional.of(result);
        }
        return Optional.empty();
    }

    // Rule 0.1: a contains b or b contains a
    private static boolean hasContainment(StandardKLine a, StandardKLine b) {
        boolean aContainsB = a.high().compareTo(b.high()) >= 0
                && a.low().compareTo(b.low()) <= 0;
        boolean bContainsA = b.high().compareTo(a.high()) >= 0
                && b.low().compareTo(a.low()) <= 0;
        return aContainsB || bContainsA;
    }

    // Rule 0.2: Direction from previous non-contained K-line
    private static Direction determineDirection(StandardKLine prev, StandardKLine curr) {
        if (curr.high().compareTo(prev.high()) > 0) {
            return Direction.UP;
        }
        if (curr.low().compareTo(prev.low()) < 0) {
            return Direction.DOWN;
        }
        return prev.direction();
    }

    // Rule 0.3: Merge based on direction
    private static StandardKLine merge(StandardKLine a, StandardKLine b, Direction direction) {
        BigDecimal newHigh;
        BigDecimal newLow;
        if (direction == Direction.UP) {
            newHigh = a.high().max(b.high());
            newLow = a.low().max(b.low());
        } else {
            newHigh = a.high().min(b.high());
            newLow = a.low().min(b.low());
        }

        return new StandardKLine(
                a.timestamp(),
                a.open(),
                newHigh,
                newLow,
                b.close(),
                a.volume() + b.volume(),
                a.originalCount() + b.originalCount(),
                direction,
                a.timeframe()
        );
    }
}
