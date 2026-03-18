package com.zenalpha.data.controller;

import com.zenalpha.common.dto.ApiResponse;
import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.RawKLine;
import com.zenalpha.data.service.MarketDataService;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/data/klines")
public class KLineController {

    private final MarketDataService marketDataService;

    public KLineController(MarketDataService marketDataService) {
        this.marketDataService = marketDataService;
    }

    @GetMapping("/{instrument}")
    public ResponseEntity<ApiResponse<List<RawKLine>>> getKLines(
            @PathVariable String instrument,
            @RequestParam(defaultValue = "1d") String timeframe,
            @RequestParam(defaultValue = "500") int limit) {
        TimeFrame tf = TimeFrame.fromCode(timeframe);
        List<RawKLine> klines = marketDataService.getKLines(instrument, tf, limit);
        return ResponseEntity.ok(ApiResponse.ok(klines));
    }

    @PostMapping("/sync")
    public ResponseEntity<ApiResponse<SyncResponse>> syncKLines(
            @RequestBody SyncRequest request) {
        TimeFrame tf = TimeFrame.fromCode(request.timeframe());
        int synced;
        if (request.from() != null && request.to() != null) {
            synced = marketDataService.syncKLines(request.instrument(), tf, request.from(), request.to());
        } else {
            synced = marketDataService.syncKLines(request.instrument(), tf);
        }
        return ResponseEntity.ok(ApiResponse.ok(new SyncResponse(request.instrument(), synced)));
    }

    public record SyncRequest(
            String instrument,
            String timeframe,
            LocalDate from,
            LocalDate to
    ) {
    }

    public record SyncResponse(
            String instrument,
            int syncedCount
    ) {
    }
}
