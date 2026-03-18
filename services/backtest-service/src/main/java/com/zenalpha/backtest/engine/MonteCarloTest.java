package com.zenalpha.backtest.engine;

import com.zenalpha.common.model.Trade;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

public class MonteCarloTest {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final int SCALE = 8;

    private MonteCarloTest() {
    }

    public record ConfidenceInterval(
            BigDecimal p5,
            BigDecimal p25,
            BigDecimal p50,
            BigDecimal p75,
            BigDecimal p95,
            BigDecimal mean,
            BigDecimal worstCase,
            BigDecimal bestCase,
            double probabilityOfProfit
    ) {
    }

    public static ConfidenceInterval run(List<Trade> trades, int numSimulations) {
        if (trades.isEmpty()) {
            return new ConfidenceInterval(
                    BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                    BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                    BigDecimal.ZERO, BigDecimal.ZERO, 0.0
            );
        }

        List<BigDecimal> pnlValues = trades.stream().map(Trade::pnl).toList();
        Random random = new Random(42);
        List<BigDecimal> simulatedReturns = new ArrayList<>(numSimulations);

        for (int sim = 0; sim < numSimulations; sim++) {
            List<BigDecimal> shuffled = new ArrayList<>(pnlValues);
            Collections.shuffle(shuffled, random);
            BigDecimal totalPnl = shuffled.stream()
                    .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
            simulatedReturns.add(totalPnl);
        }

        Collections.sort(simulatedReturns);

        int profitCount = (int) simulatedReturns.stream()
                .filter(r -> r.compareTo(BigDecimal.ZERO) > 0)
                .count();

        return new ConfidenceInterval(
                percentile(simulatedReturns, 5),
                percentile(simulatedReturns, 25),
                percentile(simulatedReturns, 50),
                percentile(simulatedReturns, 75),
                percentile(simulatedReturns, 95),
                mean(simulatedReturns),
                simulatedReturns.getFirst(),
                simulatedReturns.getLast(),
                (double) profitCount / numSimulations
        );
    }

    private static BigDecimal percentile(List<BigDecimal> sorted, int p) {
        int index = (int) Math.ceil(p / 100.0 * sorted.size()) - 1;
        index = Math.max(0, Math.min(index, sorted.size() - 1));
        return sorted.get(index);
    }

    private static BigDecimal mean(List<BigDecimal> values) {
        BigDecimal sum = values.stream().reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        return sum.divide(BigDecimal.valueOf(values.size()), SCALE, RoundingMode.HALF_UP);
    }
}
