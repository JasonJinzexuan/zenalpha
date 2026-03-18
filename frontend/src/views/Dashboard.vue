<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSignalStore } from '@/stores/signal'
import SignalTable from '@/components/SignalTable.vue'
import type { ScanResult } from '@/types'

const signalStore = useSignalStore()
const selectedTimeframe = ref<'1d' | '1w'>('1d')

const defaultInstruments = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B',
  'JPM', 'V', 'UNH', 'XOM', 'JNJ', 'WMT', 'PG', 'MA', 'HD', 'CVX',
  'MRK', 'ABBV'
]

onMounted(() => {
  signalStore.scan(defaultInstruments, selectedTimeframe.value)
})

function refreshScan() {
  signalStore.scan(defaultInstruments, selectedTimeframe.value)
}

const trendDistribution = ref<{ type: string; count: number }[]>([])

function computeDistribution(results: ScanResult[]) {
  const counts: Record<string, number> = { B1: 0, B2: 0, B3: 0, S1: 0, S2: 0, S3: 0 }
  for (const r of results) {
    const t = r.signal.signalType
    if (t in counts) counts[t]++
  }
  trendDistribution.value = Object.entries(counts).map(([type, count]) => ({ type, count }))
}
</script>

<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h2>Signal Dashboard</h2>
      <div class="controls">
        <el-radio-group v-model="selectedTimeframe" @change="refreshScan">
          <el-radio-button value="1d">Daily</el-radio-button>
          <el-radio-button value="1w">Weekly</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="signalStore.loading" @click="refreshScan">
          Refresh
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="signalStore.error"
      :title="signalStore.error"
      type="error"
      show-icon
      closable
      class="error-alert"
    />

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ signalStore.scanResults.length }}</div>
          <div class="stat-label">Total Signals</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card buy">
          <div class="stat-value">
            {{ signalStore.scanResults.filter(r => r.signal.signalType.startsWith('B')).length }}
          </div>
          <div class="stat-label">Buy Signals</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card sell">
          <div class="stat-value">
            {{ signalStore.scanResults.filter(r => r.signal.signalType.startsWith('S')).length }}
          </div>
          <div class="stat-label">Sell Signals</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">
            {{ signalStore.scanResults.length > 0
              ? (signalStore.scanResults.reduce((sum, r) => sum + r.score, 0) / signalStore.scanResults.length).toFixed(2)
              : '0.00' }}
          </div>
          <div class="stat-label">Avg Score</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="signal-card">
      <template #header>
        <span>Top Signals (sorted by score)</span>
      </template>
      <SignalTable :results="signalStore.scanResults" :loading="signalStore.loading" />
    </el-card>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-header h2 {
  color: #c9d1d9;
}

.controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.error-alert {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  background-color: #161b22;
  border-color: #30363d;
  text-align: center;
  padding: 10px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #58a6ff;
}

.stat-card.buy .stat-value {
  color: #3fb950;
}

.stat-card.sell .stat-value {
  color: #f85149;
}

.stat-label {
  color: #8b949e;
  font-size: 14px;
  margin-top: 4px;
}

.signal-card {
  background-color: #161b22;
  border-color: #30363d;
}
</style>
