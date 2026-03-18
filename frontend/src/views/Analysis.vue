<script setup lang="ts">
import { ref } from 'vue'
import { useSignalStore } from '@/stores/signal'
import KLineChart from '@/components/KLineChart.vue'
import CenterOverlay from '@/components/CenterOverlay.vue'
import type { TimeFrame } from '@/types'

const signalStore = useSignalStore()
const instrument = ref('AAPL')
const timeframe = ref<TimeFrame>('1d')

function runAnalysis() {
  signalStore.analyze(instrument.value, timeframe.value)
}

const timeframeOptions = [
  { label: '1 Min', value: '1m' },
  { label: '5 Min', value: '5m' },
  { label: '30 Min', value: '30m' },
  { label: '1 Hour', value: '1h' },
  { label: 'Daily', value: '1d' },
  { label: 'Weekly', value: '1w' },
  { label: 'Monthly', value: '1M' },
]
</script>

<template>
  <div class="analysis">
    <div class="analysis-header">
      <h2>Technical Analysis</h2>
      <div class="controls">
        <el-input
          v-model="instrument"
          placeholder="Symbol (e.g. AAPL)"
          style="width: 160px"
          @keyup.enter="runAnalysis"
        />
        <el-select v-model="timeframe" style="width: 120px">
          <el-option
            v-for="opt in timeframeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button type="primary" :loading="signalStore.loading" @click="runAnalysis">
          Analyze
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

    <template v-if="signalStore.analysisResult">
      <el-card shadow="never" class="chart-card">
        <template #header>
          <span>{{ instrument }} — {{ timeframe }} K-Line with Chan Theory Overlay</span>
        </template>
        <div class="chart-container">
          <KLineChart
            :klines="signalStore.analysisResult.klines"
            :signals="signalStore.analysisResult.signals"
            :strokes="signalStore.analysisResult.strokes"
            :segments="signalStore.analysisResult.segments"
          />
          <CenterOverlay :centers="signalStore.analysisResult.centers" />
        </div>
      </el-card>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="never" class="info-card">
            <template #header>Signals</template>
            <el-table :data="signalStore.analysisResult.signals" stripe size="small">
              <el-table-column prop="signalType" label="Type" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.signalType.startsWith('B') ? 'success' : 'danger'" size="small">
                    {{ row.signalType }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="price" label="Price" width="100" />
              <el-table-column prop="strength" label="Strength" width="100">
                <template #default="{ row }">
                  {{ (row.strength * 100).toFixed(1) }}%
                </template>
              </el-table-column>
              <el-table-column prop="reasoning" label="Reasoning" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" class="info-card">
            <template #header>Structure Summary</template>
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="Standard K-Lines">
                {{ signalStore.analysisResult.klines.length }}
              </el-descriptions-item>
              <el-descriptions-item label="Fractals">
                {{ signalStore.analysisResult.fractals.length }}
              </el-descriptions-item>
              <el-descriptions-item label="Strokes">
                {{ signalStore.analysisResult.strokes.length }}
              </el-descriptions-item>
              <el-descriptions-item label="Segments">
                {{ signalStore.analysisResult.segments.length }}
              </el-descriptions-item>
              <el-descriptions-item label="Centers">
                {{ signalStore.analysisResult.centers.length }}
              </el-descriptions-item>
              <el-descriptions-item label="Signals">
                {{ signalStore.analysisResult.signals.length }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-empty v-else-if="!signalStore.loading" description="Enter a symbol and click Analyze" />
  </div>
</template>

<style scoped>
.analysis {
  max-width: 1400px;
  margin: 0 auto;
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.analysis-header h2 {
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

.chart-card {
  background-color: #161b22;
  border-color: #30363d;
  margin-bottom: 20px;
}

.chart-container {
  position: relative;
  height: 500px;
}

.info-card {
  background-color: #161b22;
  border-color: #30363d;
}
</style>
