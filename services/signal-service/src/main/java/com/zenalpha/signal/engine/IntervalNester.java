package com.zenalpha.signal.engine;

import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.IntervalNesting;
import com.zenalpha.common.model.PipelineState;
import com.zenalpha.common.model.Signal;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

/**
 * L8: Multi-timeframe interval nesting (区间套).
 * Rules 8.1-8.3: recursive positioning, large-buy-small principle, level mapping.
 */
@Component
public class IntervalNester {

    // Rule 8.3: Level mapping
    private static final Map<TimeFrame, TimeFrame[]> LEVEL_MAP = Map.of(
            TimeFrame.MONTHLY, new TimeFrame[]{TimeFrame.WEEKLY, TimeFrame.DAILY},
            TimeFrame.WEEKLY, new TimeFrame[]{TimeFrame.DAILY, TimeFrame.MIN_30},
            TimeFrame.DAILY, new TimeFrame[]{TimeFrame.MIN_30, TimeFrame.MIN_5},
            TimeFrame.MIN_30, new TimeFrame[]{TimeFrame.MIN_5, TimeFrame.MIN_1}
    );

    public IntervalNesting nest(Map<TimeFrame, PipelineState> statesByLevel) {
        // Convert pipeline states to signal maps
        Map<TimeFrame, List<Signal>> signalsByLevel = new HashMap<>();
        for (var entry : statesByLevel.entrySet()) {
            signalsByLevel.put(entry.getKey(), entry.getValue().signals());
        }

        return nestFromSignals(signalsByLevel);
    }

    public IntervalNesting nestFromSignals(Map<TimeFrame, List<Signal>> signalsByLevel) {
        // Rule 8.1: Step through levels large → small
        for (TimeFrame largeTf : List.of(
                TimeFrame.MONTHLY, TimeFrame.WEEKLY, TimeFrame.DAILY, TimeFrame.MIN_30)) {

            TimeFrame[] subLevels = LEVEL_MAP.get(largeTf);
            if (subLevels == null) {
                continue;
            }

            List<Signal> largeSignals = signalsByLevel.getOrDefault(largeTf, List.of());
            Signal largeSig = latestSignal(largeSignals);
            if (largeSig == null) {
                continue;
            }

            TimeFrame mediumTf = subLevels[0];
            TimeFrame preciseTf = subLevels[1];

            Signal mediumSig = latestSignal(signalsByLevel.getOrDefault(mediumTf, List.of()));
            Signal preciseSig = latestSignal(signalsByLevel.getOrDefault(preciseTf, List.of()));

            // Direction alignment check
            boolean aligned = true;
            if (mediumSig != null && !signalsAligned(largeSig, mediumSig)) {
                aligned = false;
            }
            if (preciseSig != null && !signalsAligned(largeSig, preciseSig)) {
                aligned = false;
            }

            // Rule 8.2: Large=sell AND small=buy → no action (veto)
            if (isSellSignal(largeSig) && preciseSig != null && isBuySignal(preciseSig)) {
                return new IntervalNesting(
                        preciseTf,
                        largeSig,
                        mediumSig,
                        preciseSig,
                        countDepth(largeSig, mediumSig, preciseSig),
                        false,
                        BigDecimal.ZERO
                );
            }

            int depth = countDepth(largeSig, mediumSig, preciseSig);
            BigDecimal confidence = calcConfidence(depth, aligned, largeSig, mediumSig, preciseSig);

            return new IntervalNesting(
                    preciseTf,
                    largeSig,
                    mediumSig,
                    preciseSig,
                    depth,
                    aligned,
                    confidence
            );
        }

        return null;
    }

    private static Signal latestSignal(List<Signal> signals) {
        if (signals == null || signals.isEmpty()) {
            return null;
        }
        return signals.stream()
                .max(Comparator.comparing(Signal::timestamp))
                .orElse(null);
    }

    private static boolean isBuySignal(Signal sig) {
        return sig.signalType() == SignalType.B1
                || sig.signalType() == SignalType.B2
                || sig.signalType() == SignalType.B3;
    }

    private static boolean isSellSignal(Signal sig) {
        return sig.signalType() == SignalType.S1
                || sig.signalType() == SignalType.S2
                || sig.signalType() == SignalType.S3;
    }

    private static boolean signalsAligned(Signal large, Signal small) {
        return isBuySignal(large) == isBuySignal(small);
    }

    private static int countDepth(Signal large, Signal medium, Signal precise) {
        int count = 0;
        if (large != null) count++;
        if (medium != null) count++;
        if (precise != null) count++;
        return count;
    }

    private static BigDecimal calcConfidence(
            int depth, boolean aligned,
            Signal large, Signal medium, Signal precise) {

        int present = 0;
        if (large != null) present++;
        if (medium != null) present++;
        if (precise != null) present++;

        if (present == 0) {
            return BigDecimal.ZERO;
        }

        BigDecimal base = BigDecimal.valueOf(present)
                .divide(BigDecimal.valueOf(3), 2, RoundingMode.HALF_UP);

        if (aligned) {
            base = base.add(new BigDecimal("0.2"));
        }
        if (depth >= 3) {
            base = base.add(new BigDecimal("0.1"));
        }

        return base.min(BigDecimal.ONE);
    }
}
