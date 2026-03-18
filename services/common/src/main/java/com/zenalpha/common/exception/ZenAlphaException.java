package com.zenalpha.common.exception;

public class ZenAlphaException extends RuntimeException {

    private final String code;

    public ZenAlphaException(String code, String message) {
        super(message);
        this.code = code;
    }

    public ZenAlphaException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
