package com.zenalpha.common.enums;

public enum SignalType {
    B1("B1"), B2("B2"), B3("B3"),
    S1("S1"), S2("S2"), S3("S3");

    private final String code;

    SignalType(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    public boolean isBuy() {
        return this == B1 || this == B2 || this == B3;
    }

    public boolean isSell() {
        return this == S1 || this == S2 || this == S3;
    }
}
