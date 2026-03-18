package com.zenalpha.signal.entity;

import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.enums.TimeFrame;
import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "signal_record", indexes = {
        @Index(name = "idx_instrument_ts", columnList = "instrument,signalTime"),
        @Index(name = "idx_signal_type", columnList = "signalType"),
        @Index(name = "idx_created_at", columnList = "createdAt")
})
public class SignalEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 32)
    private String instrument;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 8)
    private SignalType signalType;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 8)
    private TimeFrame timeframe;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal price;

    @Column(nullable = false, precision = 10, scale = 6)
    private BigDecimal strength;

    @Column(nullable = false, precision = 10, scale = 6)
    private BigDecimal score;

    @Column(nullable = false)
    private LocalDateTime signalTime;

    @Column(length = 16)
    private String sourceLesson;

    @Column(length = 512)
    private String reasoning;

    @Column(precision = 10, scale = 6)
    private BigDecimal divergenceStrength;

    @Column(precision = 10, scale = 6)
    private BigDecimal volumeRatio;

    private boolean smallToLarge;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = LocalDateTime.now();
        }
    }

    // Getters
    public Long getId() { return id; }
    public String getInstrument() { return instrument; }
    public SignalType getSignalType() { return signalType; }
    public TimeFrame getTimeframe() { return timeframe; }
    public BigDecimal getPrice() { return price; }
    public BigDecimal getStrength() { return strength; }
    public BigDecimal getScore() { return score; }
    public LocalDateTime getSignalTime() { return signalTime; }
    public String getSourceLesson() { return sourceLesson; }
    public String getReasoning() { return reasoning; }
    public BigDecimal getDivergenceStrength() { return divergenceStrength; }
    public BigDecimal getVolumeRatio() { return volumeRatio; }
    public boolean isSmallToLarge() { return smallToLarge; }
    public LocalDateTime getCreatedAt() { return createdAt; }

    // Builder-style setters for immutable construction pattern
    public static SignalEntity create(
            String instrument, SignalType signalType, TimeFrame timeframe,
            BigDecimal price, BigDecimal strength, BigDecimal score,
            LocalDateTime signalTime, String sourceLesson, String reasoning,
            BigDecimal divergenceStrength, BigDecimal volumeRatio, boolean smallToLarge) {

        SignalEntity entity = new SignalEntity();
        entity.instrument = instrument;
        entity.signalType = signalType;
        entity.timeframe = timeframe;
        entity.price = price;
        entity.strength = strength;
        entity.score = score;
        entity.signalTime = signalTime;
        entity.sourceLesson = sourceLesson;
        entity.reasoning = reasoning;
        entity.divergenceStrength = divergenceStrength;
        entity.volumeRatio = volumeRatio;
        entity.smallToLarge = smallToLarge;
        return entity;
    }
}
