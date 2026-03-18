<script setup lang="ts">
import type { ScanResult } from '@/types'

defineProps<{
  results: ScanResult[]
  loading: boolean
}>()

function signalColor(type: string): string {
  return type.startsWith('B') ? 'success' : 'danger'
}

function formatScore(score: number): string {
  return score.toFixed(2)
}
</script>

<template>
  <el-table
    :data="results"
    v-loading="loading"
    stripe
    size="small"
    :default-sort="{ prop: 'score', order: 'descending' }"
    max-height="600"
  >
    <el-table-column prop="rank" label="#" width="50" sortable />
    <el-table-column prop="instrument" label="Symbol" width="100" sortable />
    <el-table-column label="Signal" width="80">
      <template #default="{ row }">
        <el-tag :type="signalColor(row.signal.signalType)" size="small">
          {{ row.signal.signalType }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="Price" width="100">
      <template #default="{ row }">
        {{ row.signal.price.toFixed(2) }}
      </template>
    </el-table-column>
    <el-table-column prop="score" label="Score" width="80" sortable>
      <template #default="{ row }">
        <span :style="{ color: row.score >= 70 ? '#3fb950' : row.score >= 40 ? '#d29922' : '#8b949e' }">
          {{ formatScore(row.score) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="Strength" width="100">
      <template #default="{ row }">
        <el-progress
          :percentage="Math.round(row.signal.strength * 100)"
          :stroke-width="6"
          :color="row.signal.signalType.startsWith('B') ? '#3fb950' : '#f85149'"
        />
      </template>
    </el-table-column>
    <el-table-column label="Level" width="80">
      <template #default="{ row }">
        <el-tag size="small" type="info">{{ row.signal.level }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="Nesting" width="80">
      <template #default="{ row }">
        <template v-if="row.nesting">
          <el-tag size="small" :type="row.nesting.directionAligned ? 'success' : 'warning'">
            {{ row.nesting.nestingDepth }}x
          </el-tag>
        </template>
        <span v-else class="no-nesting">-</span>
      </template>
    </el-table-column>
    <el-table-column label="Reasoning" min-width="200">
      <template #default="{ row }">
        <span class="reasoning">{{ row.signal.reasoning }}</span>
      </template>
    </el-table-column>
    <el-table-column label="Time" width="160">
      <template #default="{ row }">
        {{ row.signal.timestamp }}
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.no-nesting {
  color: #484f58;
}

.reasoning {
  color: #8b949e;
  font-size: 12px;
}
</style>
