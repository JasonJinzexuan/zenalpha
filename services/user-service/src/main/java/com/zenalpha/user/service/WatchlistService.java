package com.zenalpha.user.service;

import com.zenalpha.common.exception.ZenAlphaException;
import com.zenalpha.user.dto.WatchlistRequest;
import com.zenalpha.user.entity.WatchlistEntity;
import com.zenalpha.user.repository.WatchlistRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class WatchlistService {

    private final WatchlistRepository watchlistRepository;

    public WatchlistService(WatchlistRepository watchlistRepository) {
        this.watchlistRepository = watchlistRepository;
    }

    public List<WatchlistEntity> list(Long userId) {
        return watchlistRepository.findByUserId(userId);
    }

    public WatchlistEntity create(Long userId, WatchlistRequest request) {
        var watchlist = new WatchlistEntity();
        watchlist.setUserId(userId);
        watchlist.setName(request.name());
        watchlist.setInstruments(List.copyOf(request.instruments()));
        return watchlistRepository.save(watchlist);
    }

    public void delete(Long id) {
        if (!watchlistRepository.existsById(id)) {
            throw new ZenAlphaException("WL_001", "Watchlist not found");
        }
        watchlistRepository.deleteById(id);
    }
}
