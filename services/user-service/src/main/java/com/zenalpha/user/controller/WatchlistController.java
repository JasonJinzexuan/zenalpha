package com.zenalpha.user.controller;

import com.zenalpha.common.dto.ApiResponse;
import com.zenalpha.user.dto.WatchlistRequest;
import com.zenalpha.user.entity.WatchlistEntity;
import com.zenalpha.user.repository.UserRepository;
import com.zenalpha.user.service.WatchlistService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;
import java.util.List;

@RestController
@RequestMapping("/api/users/watchlists")
public class WatchlistController {

    private final WatchlistService watchlistService;
    private final UserRepository userRepository;

    public WatchlistController(WatchlistService watchlistService, UserRepository userRepository) {
        this.watchlistService = watchlistService;
        this.userRepository = userRepository;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<WatchlistEntity>>> list(Principal principal) {
        Long userId = resolveUserId(principal);
        return ResponseEntity.ok(ApiResponse.ok(watchlistService.list(userId)));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<WatchlistEntity>> create(
            Principal principal,
            @Valid @RequestBody WatchlistRequest request) {
        Long userId = resolveUserId(principal);
        var watchlist = watchlistService.create(userId, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.ok(watchlist));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<String>> delete(@PathVariable Long id) {
        watchlistService.delete(id);
        return ResponseEntity.ok(ApiResponse.ok("Watchlist deleted"));
    }

    private Long resolveUserId(Principal principal) {
        return userRepository.findByUsername(principal.getName())
                .orElseThrow()
                .getId();
    }
}
