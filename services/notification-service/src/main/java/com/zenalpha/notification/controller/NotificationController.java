package com.zenalpha.notification.controller;

import com.zenalpha.common.dto.ApiResponse;
import com.zenalpha.notification.dto.NotificationConfigRequest;
import com.zenalpha.notification.entity.NotificationConfigEntity;
import com.zenalpha.notification.entity.NotificationLogEntity;
import com.zenalpha.notification.repository.NotificationConfigRepository;
import com.zenalpha.notification.repository.NotificationLogRepository;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    private final NotificationConfigRepository configRepository;
    private final NotificationLogRepository logRepository;

    public NotificationController(
            NotificationConfigRepository configRepository,
            NotificationLogRepository logRepository) {
        this.configRepository = configRepository;
        this.logRepository = logRepository;
    }

    @PostMapping("/config")
    public ResponseEntity<ApiResponse<NotificationConfigEntity>> createConfig(
            @RequestHeader("X-User-Id") Long userId,
            @Valid @RequestBody NotificationConfigRequest request) {

        var config = new NotificationConfigEntity();
        config.setUserId(userId);
        config.setChannel(request.channel());
        config.setTarget(request.target());
        config.setSignalTypes(request.signalTypes());
        config.setMinScore(request.minScore());
        config.setEnabled(request.enabled());

        var saved = configRepository.save(config);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.ok(saved));
    }

    @GetMapping("/config")
    public ResponseEntity<ApiResponse<List<NotificationConfigEntity>>> getConfigs(
            @RequestHeader("X-User-Id") Long userId) {

        List<NotificationConfigEntity> configs = configRepository.findByUserId(userId);
        return ResponseEntity.ok(ApiResponse.ok(configs));
    }

    @GetMapping("/log")
    public ResponseEntity<ApiResponse<List<NotificationLogEntity>>> getLogs(
            @RequestHeader("X-User-Id") Long userId) {

        List<NotificationLogEntity> logs = logRepository.findByUserIdOrderBySentAtDesc(userId);
        return ResponseEntity.ok(ApiResponse.ok(logs));
    }
}
