<script setup lang="ts">
import { ref } from 'vue'
import { useBacktestStore } from '@/stores/backtest'
import MetricsCard from '@/components/MetricsCard.vue'

const backtestStore = useBacktestStore()

const instrument = ref('AAPL')
const startDate = ref('2023-01-01')
const endDate = ref('2024-12-31')
const initialCash = ref(100000)

function runBacktest() {
  backtestStore.run(instrument.value, startDate.value, endDate.value, initialCash.value)
}

function formatPct(value: number): string {
  return (value * 100).toFixed(2) + '%'
}

function formatCurrency(value: number): string {
  return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<template>
  <div class="backtest">
    <div class="backtest-header">
      <h2>Backtest Engine</h2>
    </div>

    <el-card shadow="never" class="config-card">
      <template #header>Backtest Configuration</template>
      <el-form label-width="120px" inline>
        <el-form-item label="Symbol">
          <el-input v-model="instrument" style="width: 140px" />
        </el-form-item>
        <el-form-item label="Start Date">
          <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="End Date">
          <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="Initial Cash">
          <el-input-number v-model="initialCash" :min="1000" :step="10000" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="backtestStore.loading" @click="runBacktest">
            Run Backtest
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="backtestStore.error"
      :title="backtestStore.error"
      type="error"
      show-icon
      closable
      class="error-alert"
    />

    <template v-if="backtestStore.result">
      <MetricsCard :metrics="backtestStore.result.metrics" />

      <el-card shadow="never" class="trades-card">
        <template #header>
          <span>Trade Log ({{ backtestStore.result.trades.length }} trades)</span>
        </template>
        <el-table :data="backtestStore.result.trades" stripe size="small" max-height="500">
          <el-table-column prop="instrument" label="Symbol" width="80" />
          <el-table-column prop="direction" label="Dir" width="60">
            <template #default="{ row }">
              <el-tag :type="row.direction === 'UP' ? 'success' : 'danger'" size="small">
                {{ row.direction === 'UP' ? 'Long' : 'Short' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="signalType" label="Signal" width="70" />
          <el-table-column prop="entryPrice" label="Entry" width="100">
            <template #default="{ row }">{{ formatCurrency(row.entryPrice) }}</template>
          </el-table-column>
          <el-table-column prop="exitPrice" label="Exit" width="100">
            <template #default="{ row }">{{ formatCurrency(row.exitPrice) }}</template>
          </el-table-column>
          <el-table-column prop="entryTime" label="Entry Time" width="160" />
          <el-table-column prop="exitTime" label="Exit Time" width="160" />
          <el-table-column prop="quantity" label="Qty" width="80" />
          <el-table-column prop="pnl" label="PnL" width="100">
            <template #default="{ row }">
              <span :style="{ color: row.pnl >= 0 ? '#3fb950' : '#f85149' }">
                {{ formatCurrency(row.pnl) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="pnlPct" label="PnL %" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.pnlPct >= 0 ? '#3fb950' : '#f85149' }">
                {{ formatPct(row.pnlPct) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="exitReason" label="Exit Reason" />
        </el-table>
      </el-card>
    </template>

    <el-empty v-else-if="!backtestStore.loading" description="Configure and run a backtest" />
  </div>
</template>

<style scoped>
.backtest {
  max-width: 1400px;
  margin: 0 auto;
}

.backtest-header {
  margin-bottom: 20px;
}

.backtest-header h2 {
  color: #c9d1d9;
}

.config-card,
.trades-card {
  background-color: #161b22;
  border-color: #30363d;
  margin-bottom: 20px;
}

.error-alert {
  margin-bottom: 20px;
}
</style>
