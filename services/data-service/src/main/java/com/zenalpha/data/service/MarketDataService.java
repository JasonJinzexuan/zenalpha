package com.zenalpha.data.service;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.RawKLine;
import com.zenalpha.data.client.PolygonClient;
import com.zenalpha.data.entity.KLineEntity;
import com.zenalpha.data.repository.KLineRepository;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class MarketDataService {

    private static final Logger log = LoggerFactory.getLogger(MarketDataService.class);

    private final KLineRepository klineRepository;
    private final PolygonClient polygonClient;

    public MarketDataService(KLineRepository klineRepository, PolygonClient polygonClient) {
        this.klineRepository = klineRepository;
        this.polygonClient = polygonClient;
    }

    public List<RawKLine> getKLines(String instrument, TimeFrame timeframe, int limit) {
        List<KLineEntity> entities = klineRepository
                .findByInstrumentAndTimeframeOrderByTimestampDesc(instrument, timeframe.getCode());

        List<KLineEntity> limited = entities.size() > limit
                ? entities.subList(0, limit)
                : entities;

        List<KLineEntity> chronological = limited.reversed();

        return chronological.stream()
                .map(KLineEntity::toRawKLine)
                .toList();
    }

    @Transactional
    public int syncKLines(String instrument, TimeFrame timeframe) {
        LocalDateTime latest = klineRepository
                .findLatestTimestamp(instrument, timeframe.getCode());

        LocalDate from = latest != null
                ? latest.toLocalDate()
                : LocalDate.now().minusYears(2);
        LocalDate to = LocalDate.now();

        log.info("Syncing klines for {} {} from {} to {}", instrument, timeframe, from, to);

        List<RawKLine> klines = polygonClient.fetchKLines(instrument, timeframe, from, to);

        if (klines.isEmpty()) {
            log.info("No new klines to sync for {}", instrument);
            return 0;
        }

        List<KLineEntity> entities = klines.stream()
                .map(k -> KLineEntity.fromRawKLine(k, instrument))
                .toList();

        int saved = 0;
        for (KLineEntity entity : entities) {
            boolean exists = klineRepository.existsByInstrumentAndTimeframeAndTimestamp(
                    entity.getInstrument(), entity.getTimeframe(), entity.getTimestamp()
            );
            if (!exists) {
                klineRepository.save(entity);
                saved++;
            }
        }

        log.info("Synced {} new klines for {} {}", saved, instrument, timeframe);
        return saved;
    }

    @Transactional
    public int syncKLines(String instrument, TimeFrame timeframe, LocalDate from, LocalDate to) {
        log.info("Syncing klines for {} {} from {} to {}", instrument, timeframe, from, to);

        List<RawKLine> klines = polygonClient.fetchKLines(instrument, timeframe, from, to);
        if (klines.isEmpty()) {
            return 0;
        }

        List<KLineEntity> entities = klines.stream()
                .map(k -> KLineEntity.fromRawKLine(k, instrument))
                .toList();

        int saved = 0;
        for (KLineEntity entity : entities) {
            boolean exists = klineRepository.existsByInstrumentAndTimeframeAndTimestamp(
                    entity.getInstrument(), entity.getTimeframe(), entity.getTimestamp()
            );
            if (!exists) {
                klineRepository.save(entity);
                saved++;
            }
        }

        log.info("Synced {} new klines for {} {}", saved, instrument, timeframe);
        return saved;
    }
}
