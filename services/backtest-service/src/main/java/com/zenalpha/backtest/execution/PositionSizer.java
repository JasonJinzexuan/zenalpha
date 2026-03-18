package com.zenalpha.backtest.execution;

import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.model.Signal;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

public class PositionSizer {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final int SCALE = 8;

    private static final BigDecimal B1_RISK_PCT = new BigDecimal("0.02");
    private static final BigDecimal B2_RISK_PCT = new BigDecimal("0.015");
    private static final BigDecimal B3_RISK_PCT = new BigDecimal("0.01");
    private static final BigDecimal ATR_MULTIPLIER = new BigDecimal("2");

    private PositionSizer() {
    }

    public static BigDecimal calculate(Signal signal, BigDecimal equity, BigDecimal atr) {
        if (atr.compareTo(BigDecimal.ZERO) <= 0 || equity.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }

        BigDecimal riskPct = getRiskPct(signal.signalType());
        BigDecimal riskAmount = equity.multiply(riskPct, MC);
        BigDecimal riskPerUnit = atr.multiply(ATR_MULTIPLIER, MC);

        BigDecimal quantity = riskAmount.divide(riskPerUnit, SCALE, RoundingMode.DOWN);

        BigDecimal maxPositionValue = equity.multiply(new BigDecimal("0.3"), MC);
        BigDecimal maxQuantity = maxPositionValue.divide(signal.price(), SCALE, RoundingMode.DOWN);

        return quantity.min(maxQuantity);
    }

    private static BigDecimal getRiskPct(SignalType signalType) {
        return switch (signalType) {
            case B1, S1 -> B1_RISK_PCT;
            case B2, S2 -> B2_RISK_PCT;
            case B3, S3 -> B3_RISK_PCT;
        };
    }
}
