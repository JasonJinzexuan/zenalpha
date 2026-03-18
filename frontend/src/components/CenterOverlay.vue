<script setup lang="ts">
import type { Center } from '@/types'

defineProps<{
  centers: Center[]
}>()

function centerStyle(center: Center): Record<string, string> {
  // These will be positioned using the chart coordinate system in practice.
  // For now, render as an overlay list.
  return {
    borderLeft: '3px solid rgba(88, 166, 255, 0.6)',
    padding: '6px 10px',
    marginBottom: '4px',
    backgroundColor: 'rgba(88, 166, 255, 0.08)',
    borderRadius: '4px',
  }
}
</script>

<template>
  <div class="center-overlay" v-if="centers.length > 0">
    <div class="overlay-title">Centers ({{ centers.length }})</div>
    <div
      v-for="(center, i) in centers"
      :key="i"
      class="center-item"
      :style="centerStyle(center)"
    >
      <div class="center-range">
        <span class="label">ZG:</span> {{ center.zg.toFixed(2) }}
        <span class="label">ZD:</span> {{ center.zd.toFixed(2) }}
      </div>
      <div class="center-range">
        <span class="label">GG:</span> {{ center.gg.toFixed(2) }}
        <span class="label">DD:</span> {{ center.dd.toFixed(2) }}
      </div>
      <div class="center-meta">
        <span class="label">Level:</span> {{ center.level }}
        <span class="label">Ext:</span> {{ center.extensionCount }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.center-overlay {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 200px;
  max-height: 400px;
  overflow-y: auto;
  background-color: rgba(22, 27, 34, 0.9);
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 8px;
  z-index: 10;
}

.overlay-title {
  color: #58a6ff;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}

.center-item {
  font-size: 11px;
  color: #c9d1d9;
}

.center-range,
.center-meta {
  display: flex;
  gap: 8px;
}

.label {
  color: #8b949e;
}
</style>
