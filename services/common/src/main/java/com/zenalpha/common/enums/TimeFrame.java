package com.zenalpha.common.enums;

public enum TimeFrame {
    MIN_1("1m"),
    MIN_5("5m"),
    MIN_30("30m"),
    HOUR_1("1h"),
    DAILY("1d"),
    WEEKLY("1w"),
    MONTHLY("1M");

    private final String code;

    TimeFrame(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public static TimeFrame fromCode(String code) {
        for (TimeFrame tf : values()) {
            if (tf.code.equals(code)) {
                return tf;
            }
        }
        throw new IllegalArgumentException("Unknown timeframe: " + code);
    }

    public TimeFrame nextLarger() {
        return switch (this) {
            case MIN_1 -> MIN_5;
            case MIN_5 -> MIN_30;
            case MIN_30 -> HOUR_1;
            case HOUR_1 -> DAILY;
            case DAILY -> WEEKLY;
            case WEEKLY -> MONTHLY;
            case MONTHLY -> MONTHLY;
        };
    }

    public TimeFrame nextSmaller() {
        return switch (this) {
            case MONTHLY -> WEEKLY;
            case WEEKLY -> DAILY;
            case DAILY -> MIN_30;
            case HOUR_1 -> MIN_30;
            case MIN_30 -> MIN_5;
            case MIN_5 -> MIN_1;
            case MIN_1 -> MIN_1;
        };
    }
}
