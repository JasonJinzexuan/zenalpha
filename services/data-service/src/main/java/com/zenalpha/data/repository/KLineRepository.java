package com.zenalpha.data.repository;

import com.zenalpha.data.entity.KLineEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public interface KLineRepository extends JpaRepository<KLineEntity, Long> {

    List<KLineEntity> findByInstrumentAndTimeframeOrderByTimestampDesc(
            String instrument, String timeframe);

    boolean existsByInstrumentAndTimeframeAndTimestamp(
            String instrument, String timeframe, LocalDateTime timestamp);

    @Query("SELECT MAX(k.timestamp) FROM KLineEntity k WHERE k.instrument = :instrument AND k.timeframe = :timeframe")
    LocalDateTime findLatestTimestamp(
            @Param("instrument") String instrument,
            @Param("timeframe") String timeframe);
}
