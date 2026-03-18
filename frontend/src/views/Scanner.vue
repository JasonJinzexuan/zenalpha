<script setup lang="ts">
import { ref } from 'vue'
import { useSignalStore } from '@/stores/signal'
import SignalTable from '@/components/SignalTable.vue'
import type { TimeFrame } from '@/types'

const signalStore = useSignalStore()

const instrumentInput = ref('')
const timeframe = ref<TimeFrame>('1d')
const minScore = ref(0)

const presets = {
  'SP500 Top 20': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 'JPM', 'V',
    'UNH', 'XOM', 'JNJ', 'WMT', 'PG', 'MA', 'HD', 'CVX', 'MRK', 'ABBV'],
  'Tech Giants': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'NFLX', 'CRM', 'ORCL'],
  'Crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD', 'ADA-USD'],
}

function loadPreset(name: string) {
  const list = presets[name as keyof typeof presets]
  if (list) {
    instrumentInput.value = list.join(', ')
  }
}

function runScan() {
  const instruments = instrumentInput.value
    .split(/[,\n]/)
    .map(s => s.trim())
    .filter(s => s.length > 0)
  if (instruments.length === 0) return
  signalStore.scan(instruments, timeframe.value)
}

const filteredResults = ref(() =>
  signalStore.scanResults.filter(r => r.score >= minScore.value)
)
</script>

<template>
  <div class="scanner">
    <div class="scanner-header">
      <h2>Market Scanner</h2>
    </div>

    <el-card shadow="never" class="config-card">
      <template #header>Scan Configuration</template>
      <el-form label-width="120px">
        <el-form-item label="Instruments">
          <el-input
            v-model="instrumentInput"
            type="textarea"
            :rows="3"
            placeholder="Enter symbols separated by commas (e.g. AAPL, MSFT, GOOGL)"
          />
        </el-form-item>
        <el-form-item label="Presets">
          <el-button-group>
            <el-button
              v-for="(_, name) in presets"
              :key="name"
              size="small"
              @click="loadPreset(name)"
            >
              {{ name }}
            </el-button>
          </el-button-group>
        </el-form-item>
        <el-form-item label="Timeframe">
          <el-select v-model="timeframe" style="width: 120px">
            <el-option label="Daily" value="1d" />
            <el-option label="Weekly" value="1w" />
            <el-option label="30 Min" value="30m" />
          </el-select>
        </el-form-item>
        <el-form-item label="Min Score">
          <el-slider v-model="minScore" :min="0" :max="100" :step="5" style="width: 300px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="signalStore.loading" @click="runScan">
            Run Scan
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="results-card">
      <template #header>
        <span>Scan Results ({{ signalStore.scanResults.length }} signals found)</span>
      </template>
      <SignalTable :results="signalStore.scanResults" :loading="signalStore.loading" />
    </el-card>
  </div>
</template>

<style scoped>
.scanner {
  max-width: 1400px;
  margin: 0 auto;
}

.scanner-header {
  margin-bottom: 20px;
}

.scanner-header h2 {
  color: #c9d1d9;
}

.config-card,
.results-card {
  background-color: #161b22;
  border-color: #30363d;
  margin-bottom: 20px;
}
</style>
