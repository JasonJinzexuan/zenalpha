package com.zenalpha.data.controller;

import com.zenalpha.common.dto.ApiResponse;
import com.zenalpha.data.entity.InstrumentEntity;
import com.zenalpha.data.service.InstrumentService;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/data/instruments")
public class InstrumentController {

    private final InstrumentService instrumentService;

    public InstrumentController(InstrumentService instrumentService) {
        this.instrumentService = instrumentService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<InstrumentEntity>>> listInstruments() {
        List<InstrumentEntity> instruments = instrumentService.list();
        return ResponseEntity.ok(ApiResponse.ok(instruments));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<InstrumentEntity>> getInstrument(@PathVariable Long id) {
        InstrumentEntity instrument = instrumentService.get(id);
        return ResponseEntity.ok(ApiResponse.ok(instrument));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<InstrumentEntity>> createInstrument(
            @RequestBody InstrumentEntity instrument) {
        InstrumentEntity created = instrumentService.create(instrument);
        return ResponseEntity.ok(ApiResponse.ok(created));
    }

    @PutMapping("/{id}")
    public ResponseEntity<ApiResponse<InstrumentEntity>> updateInstrument(
            @PathVariable Long id,
            @RequestBody InstrumentEntity instrument) {
        InstrumentEntity updated = instrumentService.update(id, instrument);
        return ResponseEntity.ok(ApiResponse.ok(updated));
    }
}
