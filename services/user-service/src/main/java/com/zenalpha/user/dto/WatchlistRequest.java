package com.zenalpha.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

public record WatchlistRequest(
        @NotBlank(message = "Watchlist name is required")
        String name,

        @NotEmpty(message = "At least one instrument is required")
        List<String> instruments
) {}
