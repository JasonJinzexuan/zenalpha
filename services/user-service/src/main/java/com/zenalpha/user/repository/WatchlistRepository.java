package com.zenalpha.user.repository;

import com.zenalpha.user.entity.WatchlistEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface WatchlistRepository extends JpaRepository<WatchlistEntity, Long> {

    List<WatchlistEntity> findByUserId(Long userId);
}
