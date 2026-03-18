package com.zenalpha.common.dto;

import com.zenalpha.common.enums.TimeFrame;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

public record ScanRequest(
        @NotEmpty List<String> instruments,
        @NotNull TimeFrame timeframe
) {
}
