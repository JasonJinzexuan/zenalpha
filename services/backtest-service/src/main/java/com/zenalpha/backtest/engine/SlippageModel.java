package com.zenalpha.backtest.engine;

import com.zenalpha.common.enums.Direction;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;

public class SlippageModel {

    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);
    private static final BigDecimal DEFAULT_SLIPPAGE_RATE = new BigDecimal("0.001");

    private SlippageModel() {
    }

    public static BigDecimal applySlippage(BigDecimal price, Direction direction,
                                            BigDecimal slippageRate) {
        BigDecimal rate = slippageRate != null ? slippageRate : DEFAULT_SLIPPAGE_RATE;
        BigDecimal slippage = price.multiply(rate, MC);

        return switch (direction) {
            case UP -> price.add(slippage, MC);
            case DOWN -> price.subtract(slippage, MC);
        };
    }

    public static BigDecimal applySlippage(BigDecimal price, Direction direction) {
        return applySlippage(price, direction, DEFAULT_SLIPPAGE_RATE);
    }
}
