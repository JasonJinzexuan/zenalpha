package com.zenalpha.data.client;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.exception.ZenAlphaException;
import com.zenalpha.common.model.RawKLine;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.util.retry.Retry;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Collections;
import java.util.List;

@Component
public class PolygonClient {

    private static final Logger log = LoggerFactory.getLogger(PolygonClient.class);
    private static final String BASE_URL = "https://api.polygon.io";

    private final WebClient webClient;
    private final String apiKey;

    public PolygonClient(@Value("${polygon.api-key:}") String apiKey) {
        this.apiKey = apiKey;
        this.webClient = WebClient.builder()
                .baseUrl(BASE_URL)
                .build();
    }

    public List<RawKLine> fetchKLines(String instrument, TimeFrame timeframe,
                                       LocalDate from, LocalDate to) {
        if (apiKey == null || apiKey.isBlank()) {
            throw new ZenAlphaException("DATA_001", "Polygon API key not configured");
        }

        PolygonTimeframe ptf = toPolygonTimeframe(timeframe);

        log.info("Fetching klines from Polygon: {} {} {}-{}", instrument, timeframe, from, to);

        PolygonAggregateResponse response = webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}")
                        .queryParam("adjusted", true)
                        .queryParam("sort", "asc")
                        .queryParam("limit", 50000)
                        .queryParam("apiKey", apiKey)
                        .build(instrument, ptf.multiplier(), ptf.timespan(),
                                from.toString(), to.toString()))
                .retrieve()
                .bodyToMono(PolygonAggregateResponse.class)
                .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
                        .maxBackoff(Duration.ofSeconds(10))
                        .doBeforeRetry(signal ->
                                log.warn("Retry #{} for Polygon API call", signal.totalRetries() + 1)))
                .block(Duration.ofSeconds(30));

        if (response == null || response.results() == null) {
            log.warn("Empty response from Polygon for {}", instrument);
            return Collections.emptyList();
        }

        return response.results().stream()
                .map(r -> toRawKLine(r, timeframe))
                .toList();
    }

    private RawKLine toRawKLine(PolygonBar bar, TimeFrame timeframe) {
        LocalDateTime timestamp = LocalDateTime.ofInstant(
                Instant.ofEpochMilli(bar.t()), ZoneOffset.UTC
        );
        return new RawKLine(
                timestamp,
                BigDecimal.valueOf(bar.o()),
                BigDecimal.valueOf(bar.h()),
                BigDecimal.valueOf(bar.l()),
                BigDecimal.valueOf(bar.c()),
                bar.v(),
                timeframe
        );
    }

    private PolygonTimeframe toPolygonTimeframe(TimeFrame tf) {
        return switch (tf) {
            case MIN_1 -> new PolygonTimeframe(1, "minute");
            case MIN_5 -> new PolygonTimeframe(5, "minute");
            case MIN_30 -> new PolygonTimeframe(30, "minute");
            case HOUR_1 -> new PolygonTimeframe(1, "hour");
            case DAILY -> new PolygonTimeframe(1, "day");
            case WEEKLY -> new PolygonTimeframe(1, "week");
            case MONTHLY -> new PolygonTimeframe(1, "month");
        };
    }

    private record PolygonTimeframe(int multiplier, String timespan) {
    }

    public record PolygonAggregateResponse(
            String ticker,
            int queryCount,
            int resultsCount,
            boolean adjusted,
            List<PolygonBar> results,
            String status,
            String requestId,
            int count
    ) {
    }

    public record PolygonBar(
            double o,   // open
            double h,   // high
            double l,   // low
            double c,   // close
            long v,     // volume
            long vw,    // volume weighted
            long t,     // timestamp millis
            int n       // number of transactions
    ) {
    }
}
