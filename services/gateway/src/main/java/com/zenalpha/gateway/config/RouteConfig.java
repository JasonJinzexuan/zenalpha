package com.zenalpha.gateway.config;

import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RouteConfig {

    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
        return builder.routes()
                .route("signal-service", r -> r
                        .path("/api/signals/**")
                        .uri("lb://signal-service"))
                .route("backtest-service", r -> r
                        .path("/api/backtest/**")
                        .uri("lb://backtest-service"))
                .route("data-service", r -> r
                        .path("/api/data/**")
                        .uri("lb://data-service"))
                .route("user-service", r -> r
                        .path("/api/users/**")
                        .uri("lb://user-service"))
                .route("notification-service", r -> r
                        .path("/api/notifications/**")
                        .uri("lb://notification-service"))
                .build();
    }
}
