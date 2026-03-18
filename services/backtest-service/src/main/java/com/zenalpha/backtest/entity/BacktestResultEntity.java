package com.zenalpha.backtest.entity;

import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "backtest_result")
public class BacktestResultEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String instrument;

    @Column(nullable = false, precision = 20, scale = 4)
    private BigDecimal initialCash;

    @Column(precision = 20, scale = 8)
    private BigDecimal totalReturn;

    @Column(precision = 20, scale = 8)
    private BigDecimal annualizedReturn;

    @Column(precision = 20, scale = 8)
    private BigDecimal sharpeRatio;

    @Column(precision = 20, scale = 8)
    private BigDecimal sortinoRatio;

    @Column(precision = 20, scale = 8)
    private BigDecimal calmarRatio;

    @Column(precision = 20, scale = 8)
    private BigDecimal maxDrawdown;

    @Column(precision = 20, scale = 8)
    private BigDecimal winRate;

    @Column(precision = 20, scale = 8)
    private BigDecimal profitFactor;

    @Column
    private int totalTrades;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "backtestResult", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<TradeEntity> trades = new ArrayList<>();

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

    public BigDecimal getInitialCash() {
        return initialCash;
    }

    public void setInitialCash(BigDecimal initialCash) {
        this.initialCash = initialCash;
    }

    public BigDecimal getTotalReturn() {
        return totalReturn;
    }

    public void setTotalReturn(BigDecimal totalReturn) {
        this.totalReturn = totalReturn;
    }

    public BigDecimal getAnnualizedReturn() {
        return annualizedReturn;
    }

    public void setAnnualizedReturn(BigDecimal annualizedReturn) {
        this.annualizedReturn = annualizedReturn;
    }

    public BigDecimal getSharpeRatio() {
        return sharpeRatio;
    }

    public void setSharpeRatio(BigDecimal sharpeRatio) {
        this.sharpeRatio = sharpeRatio;
    }

    public BigDecimal getSortinoRatio() {
        return sortinoRatio;
    }

    public void setSortinoRatio(BigDecimal sortinoRatio) {
        this.sortinoRatio = sortinoRatio;
    }

    public BigDecimal getCalmarRatio() {
        return calmarRatio;
    }

    public void setCalmarRatio(BigDecimal calmarRatio) {
        this.calmarRatio = calmarRatio;
    }

    public BigDecimal getMaxDrawdown() {
        return maxDrawdown;
    }

    public void setMaxDrawdown(BigDecimal maxDrawdown) {
        this.maxDrawdown = maxDrawdown;
    }

    public BigDecimal getWinRate() {
        return winRate;
    }

    public void setWinRate(BigDecimal winRate) {
        this.winRate = winRate;
    }

    public BigDecimal getProfitFactor() {
        return profitFactor;
    }

    public void setProfitFactor(BigDecimal profitFactor) {
        this.profitFactor = profitFactor;
    }

    public int getTotalTrades() {
        return totalTrades;
    }

    public void setTotalTrades(int totalTrades) {
        this.totalTrades = totalTrades;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public List<TradeEntity> getTrades() {
        return trades;
    }

    public void setTrades(List<TradeEntity> trades) {
        this.trades = trades;
    }
}
