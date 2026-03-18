package com.zenalpha.user.service;

import com.zenalpha.common.exception.ZenAlphaException;
import com.zenalpha.user.dto.LoginRequest;
import com.zenalpha.user.dto.LoginResponse;
import com.zenalpha.user.dto.RegisterRequest;
import com.zenalpha.user.entity.UserEntity;
import com.zenalpha.user.repository.UserRepository;
import com.zenalpha.user.security.JwtTokenProvider;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider tokenProvider;

    public AuthService(UserRepository userRepository,
                       PasswordEncoder passwordEncoder,
                       JwtTokenProvider tokenProvider) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.tokenProvider = tokenProvider;
    }

    public UserEntity register(RegisterRequest request) {
        if (userRepository.existsByUsername(request.username())) {
            throw new ZenAlphaException("AUTH_001", "Username already exists");
        }
        if (userRepository.existsByEmail(request.email())) {
            throw new ZenAlphaException("AUTH_002", "Email already exists");
        }

        var user = new UserEntity();
        user.setUsername(request.username());
        user.setEmail(request.email());
        user.setPassword(passwordEncoder.encode(request.password()));
        user.setRole("USER");

        return userRepository.save(user);
    }

    public LoginResponse login(LoginRequest request) {
        UserEntity user = userRepository.findByUsername(request.username())
                .orElseThrow(() -> new ZenAlphaException("AUTH_003", "Invalid credentials"));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new ZenAlphaException("AUTH_003", "Invalid credentials");
        }

        String token = tokenProvider.generateToken(user.getUsername(), user.getRole());
        return new LoginResponse(token, user.getUsername(), user.getRole());
    }
}
