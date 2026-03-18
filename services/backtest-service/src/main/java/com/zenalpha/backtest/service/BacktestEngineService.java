package com.zenalpha.backtest.service;

import com.zenalpha.backtest.engine.MetricsCalculator;
import com.zenalpha.backtest.engine.MonteCarloTest;
import com.zenalpha.backtest.engine.PortfolioManager;
import com.zenalpha.backtest.engine.SlippageModel;
import com.zenalpha.backtest.entity.BacktestResultEntity;
import com.zenalpha.backtest.entity.TradeEntity;
import com.zenalpha.backtest.execution.PositionSizer;
import com.zenalpha.backtest.execution.StopLossManager;
import com.zenalpha.backtest.repository.BacktestResultRepository;
import com.zenalpha.common.dto.BacktestResponse;
import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.model.*;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
public class BacktestEngineService {

    private static final Logger log = LoggerFactory.getLogger(BacktestEngineService.class);
    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final int ATR_PERIOD = 14;
    private static final int MONTE_CARLO_SIMS = 1000;

    private final BacktestResultRepository resultRepository;

    public BacktestEngineService(BacktestResultRepository resultRepository) {
        this.resultRepository = resultRepository;
    }

    @Transactional
    public BacktestResponse run(String instrument, List<RawKLine> klines,
                                 List<Signal> signals, BigDecimal initialCash) {
        log.info("Starting backtest for {} with {} klines and {} signals",
                instrument, klines.size(), signals.size());

        if (klines.size() < ATR_PERIOD + 1) {
            log.warn("Insufficient klines for backtest: {}", klines.size());
            return new BacktestResponse(BacktestMetrics.empty(), List.of(), List.of());
        }

        List<BigDecimal> atrValues = calculateATR(klines);
        PortfolioSnapshot snapshot = PortfolioManager.initial(initialCash, klines.get(0).timestamp());
        List<PortfolioSnapshot> snapshots = new ArrayList<>();
        snapshots.add(snapshot);

        BigDecimal highSinceEntry = BigDecimal.ZERO;
        int signalIdx = 0;

        for (int i = ATR_PERIOD; i < klines.size(); i++) {
            RawKLine kline = klines.get(i);
            BigDecimal currentPrice = kline.close();
            BigDecimal atr = i < atrValues.size() ? atrValues.get(i) : atrValues.get(atrValues.size() - 1);
            LocalDateTime currentTime = kline.timestamp();

            highSinceEntry = highSinceEntry.max(kline.high());

            snapshot = PortfolioManager.updateMarketPrice(snapshot, currentPrice, currentTime);

            snapshot = processExits(snapshot, currentPrice, highSinceEntry, atr, currentTime);

            while (signalIdx < signals.size()
                    && !signals.get(signalIdx).timestamp().isAfter(currentTime)) {
                Signal signal = signals.get(signalIdx);
                signalIdx++;

                if (signal.signalType().isBuy() && snapshot.positions().isEmpty()) {
                    snapshot = executeEntry(snapshot, instrument, signal, currentPrice, atr, currentTime);
                    highSinceEntry = currentPrice;
                } else if (signal.signalType().isSell() && !snapshot.positions().isEmpty()) {
                    snapshot = executeSignalExit(snapshot, currentPrice, signal, currentTime);
                }
            }

            snapshots.add(snapshot);
        }

        snapshot = closeAllPositions(snapshot, klines.get(klines.size() - 1).close(), klines.get(klines.size() - 1).timestamp());
        if (!snapshot.positions().isEmpty() || snapshot != snapshots.get(snapshots.size() - 1)) {
            snapshots.add(snapshot);
        }

        BacktestMetrics metrics = MetricsCalculator.calculate(
                snapshot.trades(), snapshots, initialCash
        );

        MonteCarloTest.ConfidenceInterval mc = MonteCarloTest.run(snapshot.trades(), MONTE_CARLO_SIMS);
        log.info("Backtest complete: {} trades, {:.2f}% return, Sharpe={}, MC P(profit)={}%",
                metrics.totalTrades(),
                metrics.totalReturn().multiply(new BigDecimal("100")),
                metrics.sharpeRatio(),
                mc.probabilityOfProfit() * 100);

        persistResult(instrument, initialCash, metrics, snapshot.trades());

        return new BacktestResponse(metrics, snapshots, snapshot.trades());
    }

    private PortfolioSnapshot processExits(PortfolioSnapshot snapshot,
                                            BigDecimal currentPrice,
                                            BigDecimal highSinceEntry,
                                            BigDecimal atr,
                                            LocalDateTime currentTime) {
        PortfolioSnapshot result = snapshot;

        for (Position position : List.copyOf(result.positions())) {
            Optional<String> exitReason = StopLossManager.checkStopLoss(
                    position, currentPrice, highSinceEntry, atr,
                    result.drawdown(), currentTime
            );

            if (exitReason.isPresent()) {
                String reason = exitReason.get();
                BigDecimal exitPrice;

                if (reason.contains("REDUCE")) {
                    BigDecimal halfQty = position.quantity()
                            .divide(new BigDecimal("2"), 8, RoundingMode.DOWN);
                    Position reducedPosition = new Position(
                            position.instrument(), position.entryPrice(),
                            position.entryTime(), halfQty,
                            position.direction(), position.stopLoss(),
                            position.trailingStop(), position.signal()
                    );
                    exitPrice = SlippageModel.applySlippage(currentPrice, Direction.DOWN);
                    result = PortfolioManager.closePosition(
                            result, position, exitPrice, reason, currentTime
                    );
                    List<Position> positions = new ArrayList<>(result.positions());
                    positions.add(reducedPosition);
                    result = new PortfolioSnapshot(
                            result.timestamp(), result.cash(), List.copyOf(positions),
                            result.trades(), result.equity(), result.drawdown(), result.peakEquity()
                    );
                } else {
                    exitPrice = SlippageModel.applySlippage(currentPrice, Direction.DOWN);
                    result = PortfolioManager.closePosition(
                            result, position, exitPrice, reason, currentTime
                    );
                }
            }
        }
        return result;
    }

    private PortfolioSnapshot executeEntry(PortfolioSnapshot snapshot,
                                            String instrument,
                                            Signal signal,
                                            BigDecimal currentPrice,
                                            BigDecimal atr,
                                            LocalDateTime currentTime) {
        BigDecimal equity = PortfolioManager.getEquity(snapshot, currentPrice);
        BigDecimal quantity = PositionSizer.calculate(signal, equity, atr);

        if (quantity.compareTo(BigDecimal.ZERO) <= 0) {
            return snapshot;
        }

        BigDecimal entryPrice = SlippageModel.applySlippage(currentPrice, Direction.UP);
        BigDecimal stopLoss = entryPrice.subtract(atr.multiply(new BigDecimal("2"), MC), MC);

        return PortfolioManager.openPosition(
                snapshot, instrument, entryPrice, quantity,
                Direction.UP, stopLoss, signal, currentTime
        );
    }

    private PortfolioSnapshot executeSignalExit(PortfolioSnapshot snapshot,
                                                 BigDecimal currentPrice,
                                                 Signal signal,
                                                 LocalDateTime currentTime) {
        PortfolioSnapshot result = snapshot;
        BigDecimal exitPrice = SlippageModel.applySlippage(currentPrice, Direction.DOWN);
        String reason = "SIGNAL_" + signal.signalType().getCode();

        for (Position position : List.copyOf(result.positions())) {
            result = PortfolioManager.closePosition(result, position, exitPrice, reason, currentTime);
        }
        return result;
    }

    private PortfolioSnapshot closeAllPositions(PortfolioSnapshot snapshot,
                                                 BigDecimal lastPrice,
                                                 LocalDateTime timestamp) {
        PortfolioSnapshot result = snapshot;
        for (Position position : List.copyOf(result.positions())) {
            result = PortfolioManager.closePosition(result, position, lastPrice, "END_OF_BACKTEST", timestamp);
        }
        return result;
    }

    private List<BigDecimal> calculateATR(List<RawKLine> klines) {
        List<BigDecimal> atrValues = new ArrayList<>();
        atrValues.add(BigDecimal.ZERO);

        List<BigDecimal> trueRanges = new ArrayList<>();
        for (int i = 1; i < klines.size(); i++) {
            RawKLine current = klines.get(i);
            RawKLine prev = klines.get(i - 1);

            BigDecimal highLow = current.high().subtract(current.low()).abs();
            BigDecimal highPrevClose = current.high().subtract(prev.close()).abs();
            BigDecimal lowPrevClose = current.low().subtract(prev.close()).abs();

            BigDecimal tr = highLow.max(highPrevClose).max(lowPrevClose);
            trueRanges.add(tr);
        }

        BigDecimal firstATR = BigDecimal.ZERO;
        for (int i = 0; i < Math.min(ATR_PERIOD, trueRanges.size()); i++) {
            firstATR = firstATR.add(trueRanges.get(i), MC);
        }
        if (!trueRanges.isEmpty()) {
            firstATR = firstATR.divide(BigDecimal.valueOf(Math.min(ATR_PERIOD, trueRanges.size())),
                    8, RoundingMode.HALF_UP);
        }

        for (int i = 1; i <= trueRanges.size(); i++) {
            if (i < ATR_PERIOD) {
                atrValues.add(firstATR);
            } else if (i == ATR_PERIOD) {
                atrValues.add(firstATR);
            } else {
                BigDecimal prevATR = atrValues.get(atrValues.size() - 1);
                BigDecimal tr = trueRanges.get(i - 1);
                BigDecimal newATR = prevATR.multiply(BigDecimal.valueOf(ATR_PERIOD - 1), MC)
                        .add(tr, MC)
                        .divide(BigDecimal.valueOf(ATR_PERIOD), 8, RoundingMode.HALF_UP);
                atrValues.add(newATR);
            }
        }

        return atrValues;
    }

    private void persistResult(String instrument, BigDecimal initialCash,
                                BacktestMetrics metrics, List<Trade> trades) {
        BacktestResultEntity entity = new BacktestResultEntity();
        entity.setInstrument(instrument);
        entity.setInitialCash(initialCash);
        entity.setTotalReturn(metrics.totalReturn());
        entity.setAnnualizedReturn(metrics.annualizedReturn());
        entity.setSharpeRatio(metrics.sharpeRatio());
        entity.setSortinoRatio(metrics.sortinoRatio());
        entity.setCalmarRatio(metrics.calmarRatio());
        entity.setMaxDrawdown(metrics.maxDrawdown());
        entity.setWinRate(metrics.winRate());
        entity.setProfitFactor(metrics.profitFactor());
        entity.setTotalTrades(metrics.totalTrades());
        entity.setCreatedAt(LocalDateTime.now());

        List<TradeEntity> tradeEntities = trades.stream()
                .map(t -> TradeEntity.fromTrade(t, entity))
                .toList();
        entity.setTrades(tradeEntities);

        resultRepository.save(entity);
    }
}
