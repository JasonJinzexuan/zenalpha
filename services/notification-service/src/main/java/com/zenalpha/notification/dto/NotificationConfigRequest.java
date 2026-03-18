package com.zenalpha.notification.dto;

import jakarta.validation.constraints.NotBlank;

public record NotificationConfigRequest(
        @NotBlank(message = "Channel is required")
        String channel,

        @NotBlank(message = "Target is required")
        String target,

        String signalTypes,

        Double minScore,

        boolean enabled
) {}
