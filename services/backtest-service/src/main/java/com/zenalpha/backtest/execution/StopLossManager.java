package com.zenalpha.backtest.execution;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.model.Position;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Optional;

public class StopLossManager {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);

    private static final BigDecimal PORTFOLIO_DD_REDUCE = new BigDecimal("0.10");
    private static final BigDecimal PORTFOLIO_DD_CLEAR = new BigDecimal("0.15");
    private static final BigDecimal TRAILING_TRIGGER_R = BigDecimal.ONE;
    private static final BigDecimal TRAILING_ATR_MULT = new BigDecimal("1.5");
    private static final int TIME_STOP_MULTIPLIER = 2;

    private StopLossManager() {
    }

    public static Optional<String> checkStopLoss(Position position,
                                                  BigDecimal currentPrice,
                                                  BigDecimal highSinceEntry,
                                                  BigDecimal atr,
                                                  BigDecimal portfolioDrawdown) {
        return checkPortfolioDrawdown(portfolioDrawdown)
                .or(() -> checkHardStop(position, currentPrice))
                .or(() -> checkTimeStop(position, LocalDateTime.now()))
                .or(() -> checkTrailingStop(position, currentPrice, highSinceEntry, atr));
    }

    public static Optional<String> checkStopLoss(Position position,
                                                  BigDecimal currentPrice,
                                                  BigDecimal highSinceEntry,
                                                  BigDecimal atr,
                                                  BigDecimal portfolioDrawdown,
                                                  LocalDateTime currentTime) {
        return checkPortfolioDrawdown(portfolioDrawdown)
                .or(() -> checkHardStop(position, currentPrice))
                .or(() -> checkTimeStop(position, currentTime))
                .or(() -> checkTrailingStop(position, currentPrice, highSinceEntry, atr));
    }

    private static Optional<String> checkPortfolioDrawdown(BigDecimal portfolioDrawdown) {
        if (portfolioDrawdown.compareTo(PORTFOLIO_DD_CLEAR) >= 0) {
            return Optional.of("PORTFOLIO_DD_CLEAR_15%");
        }
        if (portfolioDrawdown.compareTo(PORTFOLIO_DD_REDUCE) >= 0) {
            return Optional.of("PORTFOLIO_DD_REDUCE_10%");
        }
        return Optional.empty();
    }

    private static Optional<String> checkHardStop(Position position, BigDecimal currentPrice) {
        if (position.stopLoss() == null) {
            return Optional.empty();
        }
        boolean triggered = position.direction() == Direction.UP
                ? currentPrice.compareTo(position.stopLoss()) <= 0
                : currentPrice.compareTo(position.stopLoss()) >= 0;

        return triggered ? Optional.of("HARD_STOP") : Optional.empty();
    }

    private static Optional<String> checkTimeStop(Position position, LocalDateTime currentTime) {
        if (position.signal() == null || position.signal().level() == null) {
            return Optional.empty();
        }

        long periodHours = getTimeframePeriodHours(position.signal().level().getCode());
        long maxHoldingHours = periodHours * TIME_STOP_MULTIPLIER;
        Duration held = Duration.between(position.entryTime(), currentTime);

        return held.toHours() > maxHoldingHours
                ? Optional.of("TIME_STOP")
                : Optional.empty();
    }

    private static Optional<String> checkTrailingStop(Position position,
                                                       BigDecimal currentPrice,
                                                       BigDecimal highSinceEntry,
                                                       BigDecimal atr) {
        if (position.direction() != Direction.UP || atr.compareTo(BigDecimal.ZERO) <= 0) {
            return Optional.empty();
        }

        BigDecimal unrealizedR = currentPrice.subtract(position.entryPrice(), MC)
                .divide(atr, 8, RoundingMode.HALF_UP);

        if (unrealizedR.compareTo(TRAILING_TRIGGER_R) <= 0) {
            return Optional.empty();
        }

        BigDecimal trailingStop = highSinceEntry.subtract(
                atr.multiply(TRAILING_ATR_MULT, MC), MC
        );

        return currentPrice.compareTo(trailingStop) <= 0
                ? Optional.of("TRAILING_STOP")
                : Optional.empty();
    }

    private static long getTimeframePeriodHours(String code) {
        return switch (code) {
            case "1m" -> 1;
            case "5m" -> 5;
            case "30m" -> 30;
            case "1h" -> 60;
            case "1d" -> 24 * 60;
            case "1w" -> 7 * 24 * 60;
            case "1M" -> 30 * 24 * 60;
            default -> 24 * 60;
        };
    }
}
