package com.zenalpha.backtest.engine;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.model.Position;
import com.zenalpha.common.model.PortfolioSnapshot;
import com.zenalpha.common.model.Signal;
import com.zenalpha.common.model.Trade;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

public class PortfolioManager {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final int SCALE = 8;

    private PortfolioManager() {
    }

    public static PortfolioSnapshot initial(BigDecimal cash, LocalDateTime timestamp) {
        return new PortfolioSnapshot(
                timestamp, cash, List.of(), List.of(), cash, BigDecimal.ZERO, cash
        );
    }

    public static PortfolioSnapshot openPosition(PortfolioSnapshot snapshot,
                                                  String instrument,
                                                  BigDecimal price,
                                                  BigDecimal quantity,
                                                  Direction direction,
                                                  BigDecimal stopLoss,
                                                  Signal signal,
                                                  LocalDateTime timestamp) {
        BigDecimal cost = price.multiply(quantity, MC);
        BigDecimal newCash = snapshot.cash().subtract(cost, MC);

        Position position = new Position(
                instrument, price, timestamp, quantity, direction, stopLoss, null, signal
        );

        List<Position> newPositions = new ArrayList<>(snapshot.positions());
        newPositions.add(position);

        BigDecimal equity = calculateEquity(newCash, newPositions, price);
        BigDecimal peakEquity = equity.max(snapshot.peakEquity());
        BigDecimal drawdown = calculateDrawdown(equity, peakEquity);

        return new PortfolioSnapshot(
                timestamp, newCash, List.copyOf(newPositions),
                snapshot.trades(), equity, drawdown, peakEquity
        );
    }

    public static PortfolioSnapshot closePosition(PortfolioSnapshot snapshot,
                                                   Position position,
                                                   BigDecimal exitPrice,
                                                   String exitReason,
                                                   LocalDateTime timestamp) {
        BigDecimal proceeds = exitPrice.multiply(position.quantity(), MC);
        BigDecimal newCash = snapshot.cash().add(proceeds, MC);

        BigDecimal pnl = calculatePnl(position, exitPrice);
        BigDecimal pnlPct = pnl.divide(
                position.entryPrice().multiply(position.quantity(), MC), SCALE, RoundingMode.HALF_UP
        );

        Trade trade = new Trade(
                position.instrument(),
                position.direction(),
                position.entryPrice(),
                exitPrice,
                position.entryTime(),
                timestamp,
                position.quantity(),
                pnl,
                pnlPct,
                position.signal() != null ? position.signal().signalType() : null,
                exitReason
        );

        List<Position> newPositions = snapshot.positions().stream()
                .filter(p -> p != position)
                .toList();

        List<Trade> newTrades = new ArrayList<>(snapshot.trades());
        newTrades.add(trade);

        BigDecimal equity = calculateEquity(newCash, newPositions, exitPrice);
        BigDecimal peakEquity = equity.max(snapshot.peakEquity());
        BigDecimal drawdown = calculateDrawdown(equity, peakEquity);

        return new PortfolioSnapshot(
                timestamp, newCash, List.copyOf(newPositions),
                List.copyOf(newTrades), equity, drawdown, peakEquity
        );
    }

    public static PortfolioSnapshot updateMarketPrice(PortfolioSnapshot snapshot,
                                                       BigDecimal currentPrice,
                                                       LocalDateTime timestamp) {
        BigDecimal equity = calculateEquity(snapshot.cash(), snapshot.positions(), currentPrice);
        BigDecimal peakEquity = equity.max(snapshot.peakEquity());
        BigDecimal drawdown = calculateDrawdown(equity, peakEquity);

        return new PortfolioSnapshot(
                timestamp, snapshot.cash(), snapshot.positions(),
                snapshot.trades(), equity, drawdown, peakEquity
        );
    }

    public static BigDecimal getEquity(PortfolioSnapshot snapshot, BigDecimal currentPrice) {
        return calculateEquity(snapshot.cash(), snapshot.positions(), currentPrice);
    }

    public static BigDecimal getDrawdown(PortfolioSnapshot snapshot) {
        return snapshot.drawdown();
    }

    private static BigDecimal calculateEquity(BigDecimal cash, List<Position> positions,
                                               BigDecimal currentPrice) {
        BigDecimal positionValue = positions.stream()
                .map(p -> currentPrice.multiply(p.quantity(), MC))
                .reduce(BigDecimal.ZERO, (a, b) -> a.add(b, MC));
        return cash.add(positionValue, MC);
    }

    private static BigDecimal calculatePnl(Position position, BigDecimal exitPrice) {
        BigDecimal diff = position.direction() == Direction.UP
                ? exitPrice.subtract(position.entryPrice(), MC)
                : position.entryPrice().subtract(exitPrice, MC);
        return diff.multiply(position.quantity(), MC);
    }

    private static BigDecimal calculateDrawdown(BigDecimal equity, BigDecimal peakEquity) {
        if (peakEquity.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return peakEquity.subtract(equity, MC)
                .divide(peakEquity, SCALE, RoundingMode.HALF_UP);
    }
}
