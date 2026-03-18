package com.zenalpha.backtest.service;

import com.zenalpha.common.dto.BacktestResponse;
import com.zenalpha.common.model.BacktestMetrics;
import com.zenalpha.common.model.RawKLine;
import com.zenalpha.common.model.Signal;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Service
public class WalkForwardService {

    private static final Logger log = LoggerFactory.getLogger(WalkForwardService.class);

    private final BacktestEngineService backtestEngine;

    public WalkForwardService(BacktestEngineService backtestEngine) {
        this.backtestEngine = backtestEngine;
    }

    public record WalkForwardResult(
            List<BacktestMetrics> windowMetrics,
            BacktestMetrics aggregateMetrics
    ) {
    }

    public WalkForwardResult run(String instrument,
                                  List<RawKLine> klines,
                                  List<Signal> signals,
                                  BigDecimal initialCash,
                                  int windowSize,
                                  int stepSize) {
        log.info("Walk-forward: instrument={}, klines={}, window={}, step={}",
                instrument, klines.size(), windowSize, stepSize);

        if (klines.size() < windowSize) {
            log.warn("Insufficient data for walk-forward: {} < {}", klines.size(), windowSize);
            return new WalkForwardResult(List.of(), BacktestMetrics.empty());
        }

        List<BacktestMetrics> windowMetrics = new ArrayList<>();

        for (int start = 0; start + windowSize <= klines.size(); start += stepSize) {
            int end = start + windowSize;
            List<RawKLine> windowKlines = klines.subList(start, end);

            var windowStart = windowKlines.getFirst().timestamp();
            var windowEnd = windowKlines.getLast().timestamp();
            List<Signal> windowSignals = signals.stream()
                    .filter(s -> !s.timestamp().isBefore(windowStart)
                            && !s.timestamp().isAfter(windowEnd))
                    .toList();

            BacktestResponse response = backtestEngine.run(
                    instrument, windowKlines, windowSignals, initialCash
            );
            windowMetrics.add(response.metrics());

            log.info("Window [{}-{}]: return={}, sharpe={}",
                    start, end, response.metrics().totalReturn(), response.metrics().sharpeRatio());
        }

        BacktestMetrics aggregate = aggregateMetrics(windowMetrics);
        return new WalkForwardResult(windowMetrics, aggregate);
    }

    private BacktestMetrics aggregateMetrics(List<BacktestMetrics> metrics) {
        if (metrics.isEmpty()) {
            return BacktestMetrics.empty();
        }

        int count = metrics.size();
        BigDecimal countBD = BigDecimal.valueOf(count);

        BigDecimal avgReturn = average(metrics.stream().map(BacktestMetrics::totalReturn).toList(), countBD);
        BigDecimal avgAnnReturn = average(metrics.stream().map(BacktestMetrics::annualizedReturn).toList(), countBD);
        BigDecimal avgSharpe = average(metrics.stream().map(BacktestMetrics::sharpeRatio).toList(), countBD);
        BigDecimal avgSortino = average(metrics.stream().map(BacktestMetrics::sortinoRatio).toList(), countBD);
        BigDecimal avgCalmar = average(metrics.stream().map(BacktestMetrics::calmarRatio).toList(), countBD);
        BigDecimal maxDD = metrics.stream().map(BacktestMetrics::maxDrawdown)
                .reduce(BigDecimal.ZERO, BigDecimal::max);
        BigDecimal avgWinRate = average(metrics.stream().map(BacktestMetrics::winRate).toList(), countBD);
        BigDecimal avgPF = average(metrics.stream().map(BacktestMetrics::profitFactor).toList(), countBD);
        int totalTrades = metrics.stream().mapToInt(BacktestMetrics::totalTrades).sum();
        BigDecimal avgPnl = average(metrics.stream().map(BacktestMetrics::avgTradePnl).toList(), countBD);

        return new BacktestMetrics(
                avgReturn, avgAnnReturn, avgSharpe, avgSortino, avgCalmar,
                maxDD, java.time.Duration.ZERO, avgWinRate, avgPF,
                totalTrades, avgPnl, java.time.Duration.ZERO
        );
    }

    private BigDecimal average(List<BigDecimal> values, BigDecimal count) {
        BigDecimal sum = values.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.divide(count, 8, java.math.RoundingMode.HALF_UP);
    }
}
