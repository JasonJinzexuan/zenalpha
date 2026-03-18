package com.zenalpha.signal.controller;

import com.zenalpha.common.dto.*;
import com.zenalpha.signal.service.AnalysisPipelineService;
import com.zenalpha.signal.service.SignalScanService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST endpoints for signal analysis and scanning.
 */
@RestController
@RequestMapping("/api/signals")
public class SignalController {

    private final AnalysisPipelineService analysisPipelineService;
    private final SignalScanService signalScanService;

    public SignalController(
            AnalysisPipelineService analysisPipelineService,
            SignalScanService signalScanService) {
        this.analysisPipelineService = analysisPipelineService;
        this.signalScanService = signalScanService;
    }

    /**
     * POST /api/signals/analyze — Run full L0-L8 analysis on provided K-line data.
     */
    @PostMapping("/analyze")
    public ResponseEntity<ApiResponse<AnalyzeResponse>> analyze(
            @Valid @RequestBody AnalyzeRequest request) {

        AnalyzeResponse response = analysisPipelineService.analyze(request);
        return ResponseEntity.ok(ApiResponse.ok(response));
    }

    /**
     * POST /api/signals/scan — Multi-instrument signal scan with scoring.
     * Note: In production, kline data is fetched from data-service.
     * For now, accepts empty klines map (returns empty results).
     */
    @PostMapping("/scan")
    public ResponseEntity<ApiResponse<ScanResponse>> scan(
            @Valid @RequestBody ScanRequest request) {

        // In production, fetch klines from data-service via Feign/REST
        // For now, return empty results for instruments without data
        ScanResponse response = signalScanService.scan(request, Map.of());
        return ResponseEntity.ok(ApiResponse.ok(response));
    }
}
