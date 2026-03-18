package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.FractalType;
import com.zenalpha.common.model.Fractal;
import com.zenalpha.common.model.StandardKLine;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

/**
 * L1: Fractal identification (分型识别).
 * Rules 1.1-1.3: top/bottom detection with alternation enforcement.
 */
@Component
public class FractalDetector {

    public List<Fractal> detect(List<StandardKLine> klines) {
        if (klines == null || klines.size() < 3) {
            return List.of();
        }

        List<Fractal> raw = new ArrayList<>();

        for (int i = 1; i < klines.size() - 1; i++) {
            StandardKLine a = klines.get(i - 1);
            StandardKLine b = klines.get(i);
            StandardKLine c = klines.get(i + 1);

            // Rule 1.1: Top fractal
            if (b.high().compareTo(a.high()) > 0 && b.high().compareTo(c.high()) > 0) {
                raw.add(new Fractal(
                        FractalType.TOP,
                        b.timestamp(),
                        b.high(),
                        i,
                        List.of(a, b, c)
                ));
            }
            // Rule 1.2: Bottom fractal
            else if (b.low().compareTo(a.low()) < 0 && b.low().compareTo(c.low()) < 0) {
                raw.add(new Fractal(
                        FractalType.BOTTOM,
                        b.timestamp(),
                        b.low(),
                        i,
                        List.of(a, b, c)
                ));
            }
        }

        // Rule 1.3: Enforce alternation — keep higher top, lower bottom on conflict
        return applyAlternation(raw);
    }

    /**
     * Feed-based detection for streaming. Returns a fractal if confirmed.
     */
    public static Optional<Fractal> feedDetect(
            StandardKLine a, StandardKLine b, StandardKLine c,
            int middleIndex, Fractal lastFractal) {

        Fractal candidate = null;

        if (b.high().compareTo(a.high()) > 0 && b.high().compareTo(c.high()) > 0) {
            candidate = new Fractal(FractalType.TOP, b.timestamp(), b.high(),
                    middleIndex, List.of(a, b, c));
        } else if (b.low().compareTo(a.low()) < 0 && b.low().compareTo(c.low()) < 0) {
            candidate = new Fractal(FractalType.BOTTOM, b.timestamp(), b.low(),
                    middleIndex, List.of(a, b, c));
        }

        if (candidate == null) {
            return Optional.empty();
        }

        return applyAlternationSingle(candidate, lastFractal);
    }

    private static List<Fractal> applyAlternation(List<Fractal> raw) {
        if (raw.isEmpty()) {
            return List.of();
        }

        List<Fractal> result = new ArrayList<>();
        Fractal last = null;

        for (Fractal candidate : raw) {
            if (last == null) {
                last = candidate;
                result.add(candidate);
                continue;
            }

            if (candidate.type() == last.type()) {
                // Same type — keep the more extreme one
                if (candidate.type() == FractalType.TOP) {
                    if (candidate.extremeValue().compareTo(last.extremeValue()) > 0) {
                        result.set(result.size() - 1, candidate);
                        last = candidate;
                    }
                } else {
                    if (candidate.extremeValue().compareTo(last.extremeValue()) < 0) {
                        result.set(result.size() - 1, candidate);
                        last = candidate;
                    }
                }
            } else {
                // Proper alternation
                result.add(candidate);
                last = candidate;
            }
        }

        return Collections.unmodifiableList(result);
    }

    private static Optional<Fractal> applyAlternationSingle(Fractal candidate, Fractal lastFractal) {
        if (lastFractal == null) {
            return Optional.of(candidate);
        }

        if (candidate.type() == lastFractal.type()) {
            if (candidate.type() == FractalType.TOP) {
                if (candidate.extremeValue().compareTo(lastFractal.extremeValue()) > 0) {
                    return Optional.of(candidate);
                }
            } else {
                if (candidate.extremeValue().compareTo(lastFractal.extremeValue()) < 0) {
                    return Optional.of(candidate);
                }
            }
            return Optional.empty();
        }

        return Optional.of(candidate);
    }
}
