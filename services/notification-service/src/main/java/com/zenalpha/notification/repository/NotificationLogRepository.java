package com.zenalpha.notification.repository;

import com.zenalpha.notification.entity.NotificationLogEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NotificationLogRepository extends JpaRepository<NotificationLogEntity, Long> {

    List<NotificationLogEntity> findByUserIdOrderBySentAtDesc(Long userId);
}
