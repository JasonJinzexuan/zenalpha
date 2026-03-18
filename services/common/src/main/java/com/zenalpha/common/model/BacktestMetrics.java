package com.zenalpha.common.model;

import java.math.BigDecimal;
import java.time.Duration;

public record BacktestMetrics(
        BigDecimal totalReturn,
        BigDecimal annualizedReturn,
        BigDecimal sharpeRatio,
        BigDecimal sortinoRatio,
        BigDecimal calmarRatio,
        BigDecimal maxDrawdown,
        Duration maxDrawdownDuration,
        BigDecimal winRate,
        BigDecimal profitFactor,
        int totalTrades,
        BigDecimal avgTradePnl,
        Duration avgHoldingPeriod
) {
    public static BacktestMetrics empty() {
        return new BacktestMetrics(
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                Duration.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                0, BigDecimal.ZERO, Duration.ZERO
        );
    }
}
