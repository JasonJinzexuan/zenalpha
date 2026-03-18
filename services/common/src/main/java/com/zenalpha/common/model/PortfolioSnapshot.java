package com.zenalpha.common.model;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record PortfolioSnapshot(
        LocalDateTime timestamp,
        BigDecimal cash,
        List<Position> positions,
        List<Trade> trades,
        BigDecimal equity,
        BigDecimal drawdown,
        BigDecimal peakEquity
) {
}
