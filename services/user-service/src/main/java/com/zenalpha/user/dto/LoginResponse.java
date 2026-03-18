package com.zenalpha.user.dto;

public record LoginResponse(
        String token,
        String username,
        String role
) {}
