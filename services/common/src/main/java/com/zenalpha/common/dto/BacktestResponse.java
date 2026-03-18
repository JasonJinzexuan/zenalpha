package com.zenalpha.common.dto;

import com.zenalpha.common.model.BacktestMetrics;
import com.zenalpha.common.model.PortfolioSnapshot;
import com.zenalpha.common.model.Trade;

import java.util.List;

public record BacktestResponse(
        BacktestMetrics metrics,
        List<PortfolioSnapshot> snapshots,
        List<Trade> trades
) {
}
