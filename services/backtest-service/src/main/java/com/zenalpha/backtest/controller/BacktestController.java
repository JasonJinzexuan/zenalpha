package com.zenalpha.backtest.controller;

import com.zenalpha.backtest.service.BacktestEngineService;
import com.zenalpha.common.dto.ApiResponse;
import com.zenalpha.common.dto.BacktestRequest;
import com.zenalpha.common.dto.BacktestResponse;
import com.zenalpha.common.model.RawKLine;
import com.zenalpha.common.model.Signal;

import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/backtest")
public class BacktestController {

    private final BacktestEngineService backtestEngine;

    public BacktestController(BacktestEngineService backtestEngine) {
        this.backtestEngine = backtestEngine;
    }

    @PostMapping("/run")
    public ResponseEntity<ApiResponse<BacktestResponse>> runBacktest(
            @Valid @RequestBody BacktestRunRequest request) {
        BacktestResponse response = backtestEngine.run(
                request.instrument(),
                request.klines(),
                request.signals(),
                request.initialCash()
        );
        return ResponseEntity.ok(ApiResponse.ok(response));
    }

    public record BacktestRunRequest(
            String instrument,
            List<RawKLine> klines,
            List<Signal> signals,
            java.math.BigDecimal initialCash
    ) {
    }
}
