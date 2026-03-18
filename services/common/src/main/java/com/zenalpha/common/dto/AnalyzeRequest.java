package com.zenalpha.common.dto;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.RawKLine;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

public record AnalyzeRequest(
        @NotBlank String instrument,
        @NotNull TimeFrame timeframe,
        @NotEmpty List<RawKLine> klines
) {
}
