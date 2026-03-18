package com.zenalpha.common.dto;

import com.zenalpha.common.model.ScanResult;

import java.util.List;

public record ScanResponse(
        List<ScanResult> results
) {
}
