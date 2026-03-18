package com.zenalpha.common.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;
import java.time.LocalDate;

public record BacktestRequest(
        @NotBlank String instrument,
        @NotNull LocalDate startDate,
        @NotNull LocalDate endDate,
        @Positive BigDecimal initialCash
) {
}
