<script setup lang="ts">
import type { BacktestMetrics } from '@/types'

const props = defineProps<{
  metrics: BacktestMetrics
}>()

function formatPct(v: number): string {
  return (v * 100).toFixed(2) + '%'
}

function formatRatio(v: number): string {
  return v.toFixed(4)
}

interface MetricItem {
  label: string
  value: string
  color: string
}

function getMetricItems(): MetricItem[] {
  const m = props.metrics
  return [
    { label: 'Total Return', value: formatPct(m.totalReturn), color: m.totalReturn >= 0 ? '#3fb950' : '#f85149' },
    { label: 'Annualized Return', value: formatPct(m.annualizedReturn), color: m.annualizedReturn >= 0 ? '#3fb950' : '#f85149' },
    { label: 'Sharpe Ratio', value: formatRatio(m.sharpeRatio), color: m.sharpeRatio >= 1 ? '#3fb950' : m.sharpeRatio >= 0 ? '#d29922' : '#f85149' },
    { label: 'Sortino Ratio', value: formatRatio(m.sortinoRatio), color: m.sortinoRatio >= 1.5 ? '#3fb950' : '#d29922' },
    { label: 'Calmar Ratio', value: formatRatio(m.calmarRatio), color: m.calmarRatio >= 1 ? '#3fb950' : '#d29922' },
    { label: 'Max Drawdown', value: formatPct(m.maxDrawdown), color: m.maxDrawdown > -0.1 ? '#d29922' : '#f85149' },
    { label: 'Win Rate', value: formatPct(m.winRate), color: m.winRate >= 0.5 ? '#3fb950' : '#f85149' },
    { label: 'Profit Factor', value: formatRatio(m.profitFactor), color: m.profitFactor >= 1.5 ? '#3fb950' : '#d29922' },
    { label: 'Total Trades', value: String(m.totalTrades), color: '#c9d1d9' },
    { label: 'Avg Trade PnL', value: '$' + m.avgTradePnl.toFixed(2), color: m.avgTradePnl >= 0 ? '#3fb950' : '#f85149' },
  ]
}
</script>

<template>
  <el-card shadow="never" class="metrics-card">
    <template #header>
      <span>Performance Metrics</span>
    </template>
    <div class="metrics-grid">
      <div v-for="item in getMetricItems()" :key="item.label" class="metric-item">
        <div class="metric-value" :style="{ color: item.color }">{{ item.value }}</div>
        <div class="metric-label">{{ item.label }}</div>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.metrics-card {
  background-color: #161b22;
  border-color: #30363d;
  margin-bottom: 20px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.metric-item {
  text-align: center;
  padding: 12px;
  background-color: #0d1117;
  border-radius: 8px;
  border: 1px solid #21262d;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.metric-label {
  color: #8b949e;
  font-size: 12px;
}
</style>
