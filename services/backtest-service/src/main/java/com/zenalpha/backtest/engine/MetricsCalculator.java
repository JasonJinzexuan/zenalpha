package com.zenalpha.backtest.engine;

import com.zenalpha.common.model.BacktestMetrics;
import com.zenalpha.common.model.PortfolioSnapshot;
import com.zenalpha.common.model.Trade;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.Duration;
import java.util.List;

public class MetricsCalculator {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final int SCALE = 8;
    private static final BigDecimal TRADING_DAYS_PER_YEAR = new BigDecimal("252");
    private static final BigDecimal RISK_FREE_RATE = BigDecimal.ZERO;

    private MetricsCalculator() {
    }

    public static BacktestMetrics calculate(List<Trade> trades,
                                             List<PortfolioSnapshot> snapshots,
                                             BigDecimal initialCash) {
        if (trades.isEmpty()) {
            return BacktestMetrics.empty();
        }

        BigDecimal totalReturn = calculateTotalReturn(snapshots, initialCash);
        BigDecimal annualizedReturn = calculateAnnualizedReturn(totalReturn, snapshots);
        BigDecimal maxDrawdown = calculateMaxDrawdown(snapshots);
        Duration maxDrawdownDuration = calculateMaxDrawdownDuration(snapshots);
        BigDecimal winRate = calculateWinRate(trades);
        BigDecimal profitFactor = calculateProfitFactor(trades);
        BigDecimal avgTradePnl = calculateAvgTradePnl(trades);
        Duration avgHoldingPeriod = calculateAvgHoldingPeriod(trades);

        List<BigDecimal> dailyReturns = calculateDailyReturns(snapshots);
        BigDecimal sharpeRatio = calculateSharpe(dailyReturns);
        BigDecimal sortinoRatio = calculateSortino(dailyReturns);
        BigDecimal calmarRatio = calculateCalmar(annualizedReturn, maxDrawdown);

        return new BacktestMetrics(
                totalReturn, annualizedReturn, sharpeRatio, sortinoRatio, calmarRatio,
                maxDrawdown, maxDrawdownDuration, winRate, profitFactor,
                trades.size(), avgTradePnl, avgHoldingPeriod
        );
    }

    private static BigDecimal calculateTotalReturn(List<PortfolioSnapshot> snapshots,
                                                    BigDecimal initialCash) {
        if (snapshots.isEmpty() || initialCash.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal finalEquity = snapshots.getLast().equity();
        return finalEquity.subtract(initialCash, MC)
                .divide(initialCash, SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateAnnualizedReturn(BigDecimal totalReturn,
                                                         List<PortfolioSnapshot> snapshots) {
        if (snapshots.size() < 2) {
            return BigDecimal.ZERO;
        }
        long days = Duration.between(
                snapshots.getFirst().timestamp(), snapshots.getLast().timestamp()
        ).toDays();
        if (days <= 0) {
            return BigDecimal.ZERO;
        }
        double years = days / 365.25;
        double totalReturnDouble = totalReturn.doubleValue();
        double annualized = Math.pow(1.0 + totalReturnDouble, 1.0 / years) - 1.0;
        return BigDecimal.valueOf(annualized).setScale(SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateMaxDrawdown(List<PortfolioSnapshot> snapshots) {
        BigDecimal maxDD = BigDecimal.ZERO;
        for (PortfolioSnapshot s : snapshots) {
            if (s.drawdown().compareTo(maxDD) > 0) {
                maxDD = s.drawdown();
            }
        }
        return maxDD;
    }

    private static Duration calculateMaxDrawdownDuration(List<PortfolioSnapshot> snapshots) {
        Duration maxDuration = Duration.ZERO;
        int drawdownStart = -1;

        for (int i = 0; i < snapshots.size(); i++) {
            PortfolioSnapshot s = snapshots.get(i);
            if (s.drawdown().compareTo(BigDecimal.ZERO) > 0) {
                if (drawdownStart < 0) {
                    drawdownStart = i;
                }
            } else {
                if (drawdownStart >= 0) {
                    Duration d = Duration.between(
                            snapshots.get(drawdownStart).timestamp(), s.timestamp()
                    );
                    if (d.compareTo(maxDuration) > 0) {
                        maxDuration = d;
                    }
                    drawdownStart = -1;
                }
            }
        }

        if (drawdownStart >= 0) {
            Duration d = Duration.between(
                    snapshots.get(drawdownStart).timestamp(), snapshots.getLast().timestamp()
            );
            if (d.compareTo(maxDuration) > 0) {
                maxDuration = d;
            }
        }

        return maxDuration;
    }

    private static BigDecimal calculateWinRate(List<Trade> trades) {
        long wins = trades.stream()
                .filter(t -> t.pnl().compareTo(BigDecimal.ZERO) > 0)
                .count();
        return BigDecimal.valueOf(wins)
                .divide(BigDecimal.valueOf(trades.size()), SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateProfitFactor(List<Trade> trades) {
        BigDecimal grossProfit = trades.stream()
                .map(Trade::pnl)
                .filter(p -> p.compareTo(BigDecimal.ZERO) > 0)
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));

        BigDecimal grossLoss = trades.stream()
                .map(Trade::pnl)
                .filter(p -> p.compareTo(BigDecimal.ZERO) < 0)
                .map(BigDecimal::abs)
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));

        if (grossLoss.compareTo(BigDecimal.ZERO) == 0) {
            return grossProfit.compareTo(BigDecimal.ZERO) > 0
                    ? new BigDecimal("999.99")
                    : BigDecimal.ZERO;
        }

        return grossProfit.divide(grossLoss, SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateAvgTradePnl(List<Trade> trades) {
        BigDecimal totalPnl = trades.stream()
                .map(Trade::pnl)
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        return totalPnl.divide(BigDecimal.valueOf(trades.size()), SCALE, RoundingMode.HALF_UP);
    }

    private static Duration calculateAvgHoldingPeriod(List<Trade> trades) {
        long totalSeconds = trades.stream()
                .mapToLong(t -> Duration.between(t.entryTime(), t.exitTime()).getSeconds())
                .sum();
        return Duration.ofSeconds(totalSeconds / trades.size());
    }

    private static List<BigDecimal> calculateDailyReturns(List<PortfolioSnapshot> snapshots) {
        if (snapshots.size() < 2) {
            return List.of();
        }
        return java.util.stream.IntStream.range(1, snapshots.size())
                .mapToObj(i -> {
                    BigDecimal prev = snapshots.get(i - 1).equity();
                    BigDecimal curr = snapshots.get(i).equity();
                    if (prev.compareTo(BigDecimal.ZERO) == 0) {
                        return BigDecimal.ZERO;
                    }
                    return curr.subtract(prev, MC).divide(prev, SCALE, RoundingMode.HALF_UP);
                })
                .toList();
    }

    private static BigDecimal calculateSharpe(List<BigDecimal> dailyReturns) {
        if (dailyReturns.size() < 2) {
            return BigDecimal.ZERO;
        }
        BigDecimal mean = mean(dailyReturns);
        BigDecimal std = stdDev(dailyReturns, mean);
        if (std.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal dailyRf = RISK_FREE_RATE.divide(TRADING_DAYS_PER_YEAR, SCALE, RoundingMode.HALF_UP);
        BigDecimal excessReturn = mean.subtract(dailyRf, MC);
        BigDecimal annualizationFactor = BigDecimal.valueOf(Math.sqrt(TRADING_DAYS_PER_YEAR.doubleValue()));
        return excessReturn.divide(std, SCALE, RoundingMode.HALF_UP)
                .multiply(annualizationFactor, MC)
                .setScale(SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateSortino(List<BigDecimal> dailyReturns) {
        if (dailyReturns.size() < 2) {
            return BigDecimal.ZERO;
        }
        BigDecimal mean = mean(dailyReturns);
        BigDecimal downDev = downsideDeviation(dailyReturns);
        if (downDev.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal annualizationFactor = BigDecimal.valueOf(Math.sqrt(TRADING_DAYS_PER_YEAR.doubleValue()));
        return mean.divide(downDev, SCALE, RoundingMode.HALF_UP)
                .multiply(annualizationFactor, MC)
                .setScale(SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal calculateCalmar(BigDecimal annualizedReturn, BigDecimal maxDrawdown) {
        if (maxDrawdown.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return annualizedReturn.divide(maxDrawdown, SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal mean(List<BigDecimal> values) {
        BigDecimal sum = values.stream().reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        return sum.divide(BigDecimal.valueOf(values.size()), SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal stdDev(List<BigDecimal> values, BigDecimal mean) {
        BigDecimal sumSq = values.stream()
                .map(v -> v.subtract(mean, MC).pow(2, MC))
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        BigDecimal variance = sumSq.divide(
                BigDecimal.valueOf(values.size() - 1), SCALE, RoundingMode.HALF_UP
        );
        return BigDecimal.valueOf(Math.sqrt(variance.doubleValue()))
                .setScale(SCALE, RoundingMode.HALF_UP);
    }

    private static BigDecimal downsideDeviation(List<BigDecimal> returns) {
        List<BigDecimal> negatives = returns.stream()
                .filter(r -> r.compareTo(BigDecimal.ZERO) < 0)
                .toList();
        if (negatives.isEmpty()) {
            return BigDecimal.ZERO;
        }
        BigDecimal sumSq = negatives.stream()
                .map(v -> v.pow(2, MC))
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        BigDecimal variance = sumSq.divide(
                BigDecimal.valueOf(returns.size()), SCALE, RoundingMode.HALF_UP
        );
        return BigDecimal.valueOf(Math.sqrt(variance.doubleValue()))
                .setScale(SCALE, RoundingMode.HALF_UP);
    }
}
