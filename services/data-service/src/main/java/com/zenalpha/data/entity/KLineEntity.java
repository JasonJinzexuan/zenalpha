package com.zenalpha.data.entity;

import com.zenalpha.common.enums.TimeFrame;
import com.zenalpha.common.model.RawKLine;

import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "kline", uniqueConstraints = {
        @UniqueConstraint(columnNames = {"instrument", "timeframe", "timestamp"})
})
public class KLineEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String instrument;

    @Column(nullable = false)
    private String timeframe;

    @Column(nullable = false)
    private LocalDateTime timestamp;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal open;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal high;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal low;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal close;

    @Column(nullable = false)
    private long volume;

    public static KLineEntity fromRawKLine(RawKLine kline, String instrument) {
        KLineEntity entity = new KLineEntity();
        entity.setInstrument(instrument);
        entity.setTimeframe(kline.timeframe().getCode());
        entity.setTimestamp(kline.timestamp());
        entity.setOpen(kline.open());
        entity.setHigh(kline.high());
        entity.setLow(kline.low());
        entity.setClose(kline.close());
        entity.setVolume(kline.volume());
        return entity;
    }

    public RawKLine toRawKLine() {
        return new RawKLine(
                timestamp, open, high, low, close, volume,
                TimeFrame.fromCode(timeframe)
        );
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getInstrument() {
        return instrument;
    }

    public void setInstrument(String instrument) {
        this.instrument = instrument;
    }

    public String getTimeframe() {
        return timeframe;
    }

    public void setTimeframe(String timeframe) {
        this.timeframe = timeframe;
    }

    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    public BigDecimal getOpen() {
        return open;
    }

    public void setOpen(BigDecimal open) {
        this.open = open;
    }

    public BigDecimal getHigh() {
        return high;
    }

    public void setHigh(BigDecimal high) {
        this.high = high;
    }

    public BigDecimal getLow() {
        return low;
    }

    public void setLow(BigDecimal low) {
        this.low = low;
    }

    public BigDecimal getClose() {
        return close;
    }

    public void setClose(BigDecimal close) {
        this.close = close;
    }

    public long getVolume() {
        return volume;
    }

    public void setVolume(long volume) {
        this.volume = volume;
    }
}
