package com.zenalpha.backtest.repository;

import com.zenalpha.backtest.entity.BacktestResultEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface BacktestResultRepository extends JpaRepository<BacktestResultEntity, Long> {

    List<BacktestResultEntity> findByInstrumentOrderByCreatedAtDesc(String instrument);
}
