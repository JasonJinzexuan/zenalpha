package com.zenalpha.backtest.entity;

import com.zenalpha.common.enums.Direction;
import com.zenalpha.common.enums.SignalType;
import com.zenalpha.common.model.Trade;

import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "trade")
public class TradeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "backtest_result_id", nullable = false)
    private BacktestResultEntity backtestResult;

    @Column(nullable = false)
    private String instrument;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Direction direction;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal entryPrice;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal exitPrice;

    @Column(nullable = false)
    private LocalDateTime entryTime;

    @Column(nullable = false)
    private LocalDateTime exitTime;

    @Column(nullable = false, precision = 20, scale = 8)
    private BigDecimal quantity;

    @Column(precision = 20, scale = 8)
    private BigDecimal pnl;

    @Column(precision = 20, scale = 8)
    private BigDecimal pnlPct;

    @Enumerated(EnumType.STRING)
    private SignalType signalType;

    @Column
    private String exitReason;

    public static TradeEntity fromTrade(Trade trade, BacktestResultEntity backtestResult) {
        TradeEntity entity = new TradeEntity();
        entity.setBacktestResult(backtestResult);
        entity.setInstrument(trade.instrument());
        entity.setDirection(trade.direction());
        entity.setEntryPrice(trade.entryPrice());
        entity.setExitPrice(trade.exitPrice());
        entity.setEntryTime(trade.entryTime());
        entity.setExitTime(trade.exitTime());
        entity.setQuantity(trade.quantity());
        entity.setPnl(trade.pnl());
        entity.setPnlPct(trade.pnlPct());
        entity.setSignalType(trade.signalType());
        entity.setExitReason(trade.exitReason());
        return entity;
    }

    public Trade toTrade() {
        return new Trade(
                instrument, direction, entryPrice, exitPrice,
                entryTime, exitTime, quantity, pnl, pnlPct,
                signalType, exitReason
        );
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public BacktestResultEntity getBacktestResult() {
        return backtestResult;
    }

    public void setBacktestResult(BacktestResultEntity backtestResult) {
        this.backtestResult = backtestResult;
    }

    public String getInstrument() {
        return instrument;
    }

    public void setInstrument(String instrument) {
        this.instrument = instrument;
    }

    public Direction getDirection() {
        return direction;
    }

    public void setDirection(Direction direction) {
        this.direction = direction;
    }

    public BigDecimal getEntryPrice() {
        return entryPrice;
    }

    public void setEntryPrice(BigDecimal entryPrice) {
        this.entryPrice = entryPrice;
    }

    public BigDecimal getExitPrice() {
        return exitPrice;
    }

    public void setExitPrice(BigDecimal exitPrice) {
        this.exitPrice = exitPrice;
    }

    public LocalDateTime getEntryTime() {
        return entryTime;
    }

    public void setEntryTime(LocalDateTime entryTime) {
        this.entryTime = entryTime;
    }

    public LocalDateTime getExitTime() {
        return exitTime;
    }

    public void setExitTime(LocalDateTime exitTime) {
        this.exitTime = exitTime;
    }

    public BigDecimal getQuantity() {
        return quantity;
    }

    public void setQuantity(BigDecimal quantity) {
        this.quantity = quantity;
    }

    public BigDecimal getPnl() {
        return pnl;
    }

    public void setPnl(BigDecimal pnl) {
        this.pnl = pnl;
    }

    public BigDecimal getPnlPct() {
        return pnlPct;
    }

    public void setPnlPct(BigDecimal pnlPct) {
        this.pnlPct = pnlPct;
    }

    public SignalType getSignalType() {
        return signalType;
    }

    public void setSignalType(SignalType signalType) {
        this.signalType = signalType;
    }

    public String getExitReason() {
        return exitReason;
    }

    public void setExitReason(String exitReason) {
        this.exitReason = exitReason;
    }
}
