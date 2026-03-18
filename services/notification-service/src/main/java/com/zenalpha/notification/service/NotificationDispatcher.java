package com.zenalpha.notification.service;

import com.zenalpha.notification.entity.NotificationConfigEntity;
import com.zenalpha.notification.entity.NotificationLogEntity;
import com.zenalpha.notification.repository.NotificationConfigRepository;
import com.zenalpha.notification.repository.NotificationLogRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class NotificationDispatcher {

    private static final Logger log = LoggerFactory.getLogger(NotificationDispatcher.class);

    private final NotificationConfigRepository configRepository;
    private final NotificationLogRepository logRepository;
    private final EmailService emailService;
    private final WebhookService webhookService;

    public NotificationDispatcher(
            NotificationConfigRepository configRepository,
            NotificationLogRepository logRepository,
            EmailService emailService,
            WebhookService webhookService) {
        this.configRepository = configRepository;
        this.logRepository = logRepository;
        this.emailService = emailService;
        this.webhookService = webhookService;
    }

    public void dispatch(String signalType, double score, String instrument, String message) {
        List<NotificationConfigEntity> configs = configRepository.findByEnabledTrue();

        for (NotificationConfigEntity config : configs) {
            if (!matchesConfig(config, signalType, score)) {
                continue;
            }

            var logEntry = new NotificationLogEntity();
            logEntry.setUserId(config.getUserId());
            logEntry.setChannel(config.getChannel());
            logEntry.setTarget(config.getTarget());
            logEntry.setPayload(message);

            try {
                switch (config.getChannel().toLowerCase()) {
                    case "email" -> emailService.send(
                            config.getTarget(),
                            "ZenAlpha Signal: " + signalType + " on " + instrument,
                            message
                    );
                    case "webhook" -> webhookService.send(
                            config.getTarget(),
                            Map.of(
                                    "signalType", signalType,
                                    "score", score,
                                    "instrument", instrument,
                                    "message", message
                            )
                    );
                    default -> log.warn("Unknown channel: {}", config.getChannel());
                }
                logEntry.setStatus("SENT");
            } catch (Exception e) {
                log.error("Notification dispatch failed for config {}: {}", config.getId(), e.getMessage());
                logEntry.setStatus("FAILED");
                logEntry.setErrorMessage(e.getMessage());
            }

            logRepository.save(logEntry);
        }
    }

    private boolean matchesConfig(NotificationConfigEntity config, String signalType, double score) {
        if (config.getMinScore() != null && score < config.getMinScore()) {
            return false;
        }
        if (config.getSignalTypes() != null && !config.getSignalTypes().isEmpty()) {
            String[] allowed = config.getSignalTypes().split(",");
            boolean found = false;
            for (String type : allowed) {
                if (type.trim().equalsIgnoreCase(signalType)) {
                    found = true;
                    break;
                }
            }
            return found;
        }
        return true;
    }
}
