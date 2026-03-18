package com.zenalpha.signal.engine;

import com.zenalpha.common.model.MACDValue;
import com.zenalpha.common.model.StandardKLine;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * L0 MACD(12,26,9) calculator using incremental EMA.
 * Uses double internally for EMA performance, outputs BigDecimal.
 */
@Component
public class MACDCalculator {

    private static final int FAST_PERIOD = 12;
    private static final int SLOW_PERIOD = 26;
    private static final int SIGNAL_PERIOD = 9;
    private static final int SCALE = 8;

    public List<MACDValue> compute(List<StandardKLine> klines) {
        if (klines == null || klines.isEmpty()) {
            return List.of();
        }

        double fastMultiplier = 2.0 / (FAST_PERIOD + 1);
        double slowMultiplier = 2.0 / (SLOW_PERIOD + 1);
        double signalMultiplier = 2.0 / (SIGNAL_PERIOD + 1);

        Double fastEma = null;
        Double slowEma = null;
        Double signalEma = null;
        double fastSum = 0.0;
        double slowSum = 0.0;
        int count = 0;

        List<MACDValue> result = new ArrayList<>(klines.size());

        for (StandardKLine kline : klines) {
            double price = kline.close().doubleValue();
            count++;

            if (count <= FAST_PERIOD) {
                fastSum += price;
            }
            if (count <= SLOW_PERIOD) {
                slowSum += price;
            }

            if (count == FAST_PERIOD) {
                fastEma = fastSum / FAST_PERIOD;
            } else if (fastEma != null) {
                fastEma = price * fastMultiplier + fastEma * (1.0 - fastMultiplier);
            }

            if (count == SLOW_PERIOD) {
                slowEma = slowSum / SLOW_PERIOD;
            } else if (slowEma != null) {
                slowEma = price * slowMultiplier + slowEma * (1.0 - slowMultiplier);
            }

            if (fastEma == null || slowEma == null) {
                result.add(MACDValue.ZERO);
                continue;
            }

            double dif = fastEma - slowEma;

            if (signalEma == null) {
                signalEma = dif;
            } else {
                signalEma = dif * signalMultiplier + signalEma * (1.0 - signalMultiplier);
            }

            double dea = signalEma;
            double histogram = 2.0 * (dif - dea);

            result.add(new MACDValue(
                    toBigDecimal(dif),
                    toBigDecimal(dea),
                    toBigDecimal(histogram)
            ));
        }

        return Collections.unmodifiableList(result);
    }

    public static BigDecimal macdArea(List<MACDValue> values, int start, int end) {
        if (values == null || values.isEmpty() || start >= end) {
            return BigDecimal.ZERO;
        }
        int s = Math.max(0, start);
        int e = Math.min(values.size(), end);
        BigDecimal total = BigDecimal.ZERO;
        for (int i = s; i < e; i++) {
            total = total.add(values.get(i).histogram().abs());
        }
        return total;
    }

    private static BigDecimal toBigDecimal(double value) {
        return BigDecimal.valueOf(value).setScale(SCALE, RoundingMode.HALF_UP);
    }
}
