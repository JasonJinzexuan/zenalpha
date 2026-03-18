package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.FractalType;
import com.zenalpha.common.model.Fractal;
import com.zenalpha.common.model.MACDValue;
import com.zenalpha.common.model.Stroke;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * L2: Stroke construction (笔的划分).
 * Rules 2.1-2.2: alternating fractals with ≥5 klines, MACD area calc.
 */
@Component
public class StrokeBuilder {

    private static final int MIN_KLINE_GAP = 4; // index diff ≥ 4 means ≥ 5 klines

    public List<Stroke> build(List<Fractal> fractals, List<MACDValue> macdValues) {
        if (fractals == null || fractals.size() < 2) {
            return List.of();
        }

        List<Stroke> strokes = new ArrayList<>();
        Fractal start = fractals.get(0);

        for (int i = 1; i < fractals.size(); i++) {
            Fractal end = fractals.get(i);

            if (isValidPair(start, end) && isDirectionCorrect(start, end)) {
                Stroke stroke = makeStroke(start, end);
                stroke = attachMacdArea(stroke, macdValues);
                strokes.add(stroke);
                start = end;
            } else if (end.type() == start.type()) {
                // Same type — keep more extreme
                if (end.type() == FractalType.TOP) {
                    if (end.extremeValue().compareTo(start.extremeValue()) > 0) {
                        start = end;
                    }
                } else {
                    if (end.extremeValue().compareTo(start.extremeValue()) < 0) {
                        start = end;
                    }
                }
            } else {
                start = end;
            }
        }

        return Collections.unmodifiableList(strokes);
    }

    // Rule 2.1: Valid pair checks
    private static boolean isValidPair(Fractal start, Fractal end) {
        if (start.type() == end.type()) {
            return false;
        }
        return Math.abs(end.klineIndex() - start.klineIndex()) >= MIN_KLINE_GAP;
    }

    private static boolean isDirectionCorrect(Fractal start, Fractal end) {
        if (start.type() == FractalType.BOTTOM && end.type() == FractalType.TOP) {
            return end.extremeValue().compareTo(start.extremeValue()) > 0;
        }
        if (start.type() == FractalType.TOP && end.type() == FractalType.BOTTOM) {
            return end.extremeValue().compareTo(start.extremeValue()) < 0;
        }
        return false;
    }

    private static Stroke makeStroke(Fractal start, Fractal end) {
        Direction direction;
        BigDecimal high;
        BigDecimal low;

        if (start.type() == FractalType.BOTTOM) {
            direction = Direction.UP;
            high = end.extremeValue();
            low = start.extremeValue();
        } else {
            direction = Direction.DOWN;
            high = start.extremeValue();
            low = end.extremeValue();
        }

        int klineCount = Math.abs(end.klineIndex() - start.klineIndex()) + 1;

        return new Stroke(
                direction,
                start,
                end,
                high,
                low,
                klineCount,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                start.timestamp(),
                end.timestamp()
        );
    }

    // Rule 2.2: Attach MACD area for divergence analysis
    private static Stroke attachMacdArea(Stroke stroke, List<MACDValue> macdValues) {
        if (macdValues == null || macdValues.isEmpty()) {
            return stroke;
        }

        int startIdx = stroke.startFractal().klineIndex();
        int endIdx = stroke.endFractal().klineIndex();

        if (startIdx >= endIdx) {
            return stroke;
        }

        int s = Math.max(0, startIdx);
        int e = Math.min(macdValues.size(), endIdx);

        BigDecimal area = BigDecimal.ZERO;
        for (int i = s; i < e; i++) {
            area = area.add(macdValues.get(i).histogram().abs());
        }

        BigDecimal difStart = s < macdValues.size()
                ? macdValues.get(s).dif() : BigDecimal.ZERO;
        BigDecimal difEnd = e > 0 && e - 1 < macdValues.size()
                ? macdValues.get(e - 1).dif() : BigDecimal.ZERO;

        return new Stroke(
                stroke.direction(),
                stroke.startFractal(),
                stroke.endFractal(),
                stroke.high(),
                stroke.low(),
                stroke.klineCount(),
                area,
                difStart,
                difEnd,
                stroke.startTime(),
                stroke.endTime()
        );
    }
}
