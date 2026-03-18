package com.zenalpha.signal.repository;

import com.zenalpha.common.enums.SignalType;
import com.zenalpha.signal.entity.SignalEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

@Repository
public interface SignalRepository extends JpaRepository<SignalEntity, Long> {

    List<SignalEntity> findByInstrumentOrderBySignalTimeDesc(String instrument);

    List<SignalEntity> findByInstrumentAndSignalTypeOrderBySignalTimeDesc(
            String instrument, SignalType signalType);

    List<SignalEntity> findBySignalTimeAfterOrderByScoreDesc(LocalDateTime after);

    List<SignalEntity> findByInstrumentAndSignalTimeAfter(
            String instrument, LocalDateTime after);
}
