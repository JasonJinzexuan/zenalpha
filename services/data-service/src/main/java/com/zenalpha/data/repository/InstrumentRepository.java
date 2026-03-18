package com.zenalpha.data.repository;

import com.zenalpha.data.entity.InstrumentEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface InstrumentRepository extends JpaRepository<InstrumentEntity, Long> {

    Optional<InstrumentEntity> findBySymbol(String symbol);

    List<InstrumentEntity> findAllByActiveTrue();
}
