<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createChart, type IChartApi, type ISeriesApi, ColorType, LineStyle } from 'lightweight-charts'
import type { StandardKLine, Signal, Stroke, Segment } from '@/types'

const props = defineProps<{
  klines: StandardKLine[]
  signals?: Signal[]
  strokes?: Stroke[]
  segments?: Segment[]
}>()

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null

function toTimestamp(ts: string): number {
  return Math.floor(new Date(ts).getTime() / 1000)
}

function initChart() {
  if (!chartContainer.value) return

  chart = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: '#0d1117' },
      textColor: '#8b949e',
    },
    grid: {
      vertLines: { color: '#21262d' },
      horzLines: { color: '#21262d' },
    },
    crosshair: {
      mode: 0,
    },
    rightPriceScale: {
      borderColor: '#30363d',
    },
    timeScale: {
      borderColor: '#30363d',
      timeVisible: true,
    },
    width: chartContainer.value.clientWidth,
    height: 450,
  })

  candleSeries = chart.addCandlestickSeries({
    upColor: '#3fb950',
    downColor: '#f85149',
    borderDownColor: '#f85149',
    borderUpColor: '#3fb950',
    wickDownColor: '#f85149',
    wickUpColor: '#3fb950',
  })

  volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  })

  chart.priceScale('volume').applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  })

  updateData()
}

function updateData() {
  if (!candleSeries || !volumeSeries) return

  const candleData = props.klines.map(k => ({
    time: toTimestamp(k.timestamp) as any,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  }))

  const volumeData = props.klines.map(k => ({
    time: toTimestamp(k.timestamp) as any,
    value: k.volume,
    color: k.close >= k.open ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)',
  }))

  candleSeries.setData(candleData)
  volumeSeries.setData(volumeData)

  // Signal markers
  if (props.signals && props.signals.length > 0) {
    const markers = props.signals.map(s => ({
      time: toTimestamp(s.timestamp) as any,
      position: s.signalType.startsWith('B') ? 'belowBar' as const : 'aboveBar' as const,
      color: s.signalType.startsWith('B') ? '#3fb950' : '#f85149',
      shape: s.signalType.startsWith('B') ? 'arrowUp' as const : 'arrowDown' as const,
      text: s.signalType,
    }))
    candleSeries.setMarkers(markers)
  }

  // Stroke lines
  if (props.strokes && props.strokes.length > 0 && chart) {
    for (const stroke of props.strokes) {
      if (!stroke.startTime || !stroke.endTime) continue
      const line = candleSeries.createPriceLine({
        price: stroke.direction === 'UP' ? stroke.high : stroke.low,
        color: stroke.direction === 'UP' ? '#58a6ff' : '#f0883e',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: false,
      })
    }
  }

  chart?.timeScale().fitContent()
}

function handleResize() {
  if (chart && chartContainer.value) {
    chart.applyOptions({ width: chartContainer.value.clientWidth })
  }
}

watch(() => props.klines, updateData, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.remove()
  chart = null
})
</script>

<template>
  <div ref="chartContainer" class="kline-chart" />
</template>

<style scoped>
.kline-chart {
  width: 100%;
  height: 450px;
}
</style>
