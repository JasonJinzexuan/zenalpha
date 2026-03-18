package com.zenalpha.notification.repository;

import com.zenalpha.notification.entity.NotificationConfigEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NotificationConfigRepository extends JpaRepository<NotificationConfigEntity, Long> {

    List<NotificationConfigEntity> findByUserId(Long userId);

    List<NotificationConfigEntity> findByEnabledTrue();
}
