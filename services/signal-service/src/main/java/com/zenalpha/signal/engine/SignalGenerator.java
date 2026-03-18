package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.DivergenceType;
import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.enums.TrendClass;
import com.zenalpha.common.model.*;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * L7: Buy/sell signal generation (三类买卖点).
 * B1/S1 (trend divergence), B2/S2 (3 conditions), B3/S3 (center breakout).
 */
@Component
public class SignalGenerator {

    private static final BigDecimal B2_STRENGTH = new BigDecimal("0.7");
    private static final BigDecimal B2_SMALL_STRENGTH = new BigDecimal("0.6");
    private static final BigDecimal B3_STRENGTH = new BigDecimal("0.5");

    public List<Signal> generate(
            TrendType trend,
            List<Divergence> divergences,
            List<Center> centers,
            List<Segment> segments,
            List<Stroke> strokes,
            String instrument) {

        List<Signal> signals = new ArrayList<>();

        // B1/S1: Trend divergence reversal
        for (Divergence div : divergences) {
            signals.addAll(generateB1S1(trend, div, instrument));
        }

        // B2/S2: Second buy/sell point (3 trigger conditions)
        Divergence latestDiv = divergences.isEmpty() ? null : divergences.get(divergences.size() - 1);
        signals.addAll(generateB2S2(trend, latestDiv, segments, centers, signals, instrument));

        // B3/S3: Third buy/sell point (center breakout)
        signals.addAll(generateB3S3(centers, strokes, instrument, trend));

        return List.copyOf(signals);
    }

    // ── B1/S1: Trend divergence → reversal ──────────────────────────

    private static List<Signal> generateB1S1(
            TrendType trend, Divergence divergence, String instrument) {

        if (divergence.type() != DivergenceType.TREND) {
            return List.of();
        }

        Segment segC = divergence.segmentC();
        if (segC.endTime() == null) {
            return List.of();
        }

        // B1: Down trend + bottom divergence → buy reversal
        if (trend.classification() == TrendClass.DOWN_TREND) {
            return List.of(new Signal(
                    SignalType.B1,
                    trend.level(),
                    instrument,
                    segC.endTime(),
                    segC.low(),
                    divergence,
                    null,
                    false,
                    divergence.strength(),
                    "L7.1",
                    "下跌趋势背驰，产生第一类买点"
            ));
        }

        // S1: Up trend + top divergence → sell reversal
        if (trend.classification() == TrendClass.UP_TREND) {
            return List.of(new Signal(
                    SignalType.S1,
                    trend.level(),
                    instrument,
                    segC.endTime(),
                    segC.high(),
                    divergence,
                    null,
                    false,
                    divergence.strength(),
                    "L7.1",
                    "上涨趋势背驰，产生第一类卖点"
            ));
        }

        return List.of();
    }

    // ── B2/S2: Three trigger conditions ─────────────────────────────

    private static List<Signal> generateB2S2(
            TrendType trend,
            Divergence divergence,
            List<Segment> segments,
            List<Center> centers,
            List<Signal> priorSignals,
            String instrument) {

        List<Signal> signals = new ArrayList<>();

        // Condition 1: B1 then no new low / S1 then no new high
        List<Signal> b1Signals = priorSignals.stream()
                .filter(s -> s.signalType() == SignalType.B1).toList();
        List<Signal> s1Signals = priorSignals.stream()
                .filter(s -> s.signalType() == SignalType.S1).toList();

        for (Signal b1 : b1Signals) {
            if (!segments.isEmpty()) {
                Segment recent = segments.get(segments.size() - 1);
                if (recent.low().compareTo(b1.price()) >= 0 && recent.endTime() != null) {
                    signals.add(new Signal(
                            SignalType.B2, trend.level(), instrument,
                            recent.endTime(), recent.low(),
                            divergence, null, false, B2_STRENGTH,
                            "L7.2", "B1后不创新低，产生第二类买点"
                    ));
                }
            }
        }

        for (Signal s1 : s1Signals) {
            if (!segments.isEmpty()) {
                Segment recent = segments.get(segments.size() - 1);
                if (recent.high().compareTo(s1.price()) <= 0 && recent.endTime() != null) {
                    signals.add(new Signal(
                            SignalType.S2, trend.level(), instrument,
                            recent.endTime(), recent.high(),
                            divergence, null, false, B2_STRENGTH,
                            "L7.2", "S1后不创新高，产生第二类卖点"
                    ));
                }
            }
        }

        // Condition 2: Consolidation divergence
        if (divergence != null && divergence.type() == DivergenceType.CONSOLIDATION) {
            Segment segC = divergence.segmentC();
            if (segC.endTime() != null) {
                if (segC.direction() == Direction.DOWN) {
                    signals.add(new Signal(
                            SignalType.B2, trend.level(), instrument,
                            segC.endTime(), segC.low(),
                            divergence, null, false, divergence.strength(),
                            "L7.2", "盘整背驰，产生第二类买点"
                    ));
                } else {
                    signals.add(new Signal(
                            SignalType.S2, trend.level(), instrument,
                            segC.endTime(), segC.high(),
                            divergence, null, false, divergence.strength(),
                            "L7.2", "盘整背驰，产生第二类卖点"
                    ));
                }
            }
        }

        // Condition 3: Small-to-large (小转大)
        if (!segments.isEmpty() && !centers.isEmpty()) {
            Segment lastSeg = segments.get(segments.size() - 1);
            Center lastCenter = centers.get(centers.size() - 1);
            if (isSmallToLarge(lastSeg, lastCenter) && lastSeg.endTime() != null) {
                SignalType sigType = lastSeg.direction() == Direction.DOWN
                        ? SignalType.B2 : SignalType.S2;
                BigDecimal price = lastSeg.direction() == Direction.DOWN
                        ? lastSeg.low() : lastSeg.high();
                signals.add(new Signal(
                        sigType, trend.level(), instrument,
                        lastSeg.endTime(), price,
                        null, lastCenter, true, B2_SMALL_STRENGTH,
                        "L7.2", "小转大，产生第二类买卖点"
                ));
            }
        }

        return signals;
    }

    private static boolean isSmallToLarge(Segment seg, Center center) {
        if (center.startTime() == null || center.endTime() == null || seg.endTime() == null) {
            return false;
        }
        return !seg.endTime().isBefore(center.startTime())
                && !seg.endTime().isAfter(center.endTime());
    }

    // ── B3/S3: Center breakout ──────────────────────────────────────

    private static List<Signal> generateB3S3(
            List<Center> centers,
            List<Stroke> strokes,
            String instrument,
            TrendType trend) {

        if (centers.isEmpty() || strokes.size() < 2) {
            return List.of();
        }

        List<Signal> signals = new ArrayList<>();
        Center center = centers.get(centers.size() - 1);

        for (int i = 0; i < strokes.size() - 1; i++) {
            Stroke curr = strokes.get(i);
            Stroke nxt = strokes.get(i + 1);

            // B3: Break above ZG, pullback low stays above ZG (first pullback only)
            if (curr.direction() == Direction.UP
                    && curr.high().compareTo(center.zg()) > 0
                    && nxt.direction() == Direction.DOWN
                    && nxt.low().compareTo(center.zg()) >= 0
                    && nxt.endTime() != null) {
                signals.add(new Signal(
                        SignalType.B3, trend.level(), instrument,
                        nxt.endTime(), nxt.low(),
                        null, center, false, B3_STRENGTH,
                        "L7.3", "突破中枢上沿后回踩不破，产生第三类买点"
                ));
                break;
            }

            // S3: Break below ZD, pullback high stays below ZD (first pullback only)
            if (curr.direction() == Direction.DOWN
                    && curr.low().compareTo(center.zd()) < 0
                    && nxt.direction() == Direction.UP
                    && nxt.high().compareTo(center.zd()) <= 0
                    && nxt.endTime() != null) {
                signals.add(new Signal(
                        SignalType.S3, trend.level(), instrument,
                        nxt.endTime(), nxt.high(),
                        null, center, false, B3_STRENGTH,
                        "L7.3", "跌破中枢下沿后反弹不回，产生第三类卖点"
                ));
                break;
            }
        }

        return signals;
    }
}
