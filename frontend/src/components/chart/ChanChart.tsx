import { useRef, useEffect, useCallback, useState } from 'react'
import {
  createChart, type IChartApi, type ISeriesApi,
  ColorType, CrosshairMode,
  CandlestickSeries, HistogramSeries, LineSeries,
  createSeriesMarkers,
  type CandlestickData, type HistogramData, type LineData, type Time,
} from 'lightweight-charts'
import { getKLines } from '@/api/data'
import { analyzeInstrument } from '@/api/agent'
import type {
  KLineData, TimeFrame, AnalysisResult,
  FractalData, StrokeData, SegmentData, CenterData, MACDData,
  OverlayLayer,
} from '@/types/chan'
import { getSignalType, isBuySignal } from '@/types/chan'
import { cn } from '@/lib/cn'

interface ChanChartProps {
  instrument: string
  timeframe?: TimeFrame
  limit?: number
  height?: number
  showVolume?: boolean
  showMACD?: boolean
  defaultLayers?: OverlayLayer[]
  onAnalysisComplete?: (result: AnalysisResult) => void
  className?: string
  compact?: boolean  // for nesting map thumbnails
}

const C = {
  bg: '#0a0a12',
  grid: 'rgba(0,240,255,0.03)',
  border: '#1a1a2e',
  up: '#00ff9f',
  down: '#ff3366',
  vol_up: 'rgba(0,255,159,0.15)',
  vol_down: 'rgba(255,51,102,0.15)',
  stroke: '#4488ff',
  segment: '#b040ff',
  center_fill: 'rgba(255,204,0,0.08)',
  center_border: 'rgba(255,204,0,0.35)',
  fractal_top: '#ff9500',
  fractal_bottom: '#00f0ff',
  buy: '#00ff9f',
  sell: '#ff3366',
  macd_pos: 'rgba(0,255,159,0.6)',
  macd_neg: 'rgba(255,51,102,0.6)',
  dif: '#4488ff',
  dea: '#ff9500',
  div_a: 'rgba(68,136,255,0.3)',
  div_c: 'rgba(255,51,102,0.3)',
}

const ALL_LAYERS: { key: OverlayLayer; label: string; color: string }[] = [
  { key: 'fractals', label: '分型', color: C.fractal_top },
  { key: 'strokes', label: '笔', color: C.stroke },
  { key: 'segments', label: '线段', color: C.segment },
  { key: 'centers', label: '中枢', color: C.center_border },
  { key: 'signals', label: '买卖点', color: C.buy },
  { key: 'divergence', label: '背驰', color: C.div_c },
]

export default function ChanChart({
  instrument, timeframe = '1d', limit = 500,
  height = 500, showVolume = true, showMACD = false,
  defaultLayers = ['strokes', 'segments', 'centers', 'signals'],
  onAnalysisComplete, className = '', compact = false,
}: ChanChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const macdContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const macdChartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState('')
  const [layers, setLayers] = useState<Set<OverlayLayer>>(new Set(defaultLayers))
  const [hoverInfo, setHoverInfo] = useState<string | null>(null)
  const overlaySeriesRef = useRef<ISeriesApi<any>[]>([])
  const klineDataRef = useRef<KLineData[]>([])

  const toggleLayer = (layer: OverlayLayer) => {
    setLayers(prev => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })
  }

  // Convert timestamp to chart Time
  const toTime = (ts: string): Time =>
    (Math.floor(new Date(ts).getTime() / 1000)) as Time

  // Map kline index to timestamp
  const indexToTime = useCallback((idx: number): Time => {
    const klines = klineDataRef.current
    if (idx >= 0 && idx < klines.length) return toTime(klines[idx].timestamp)
    if (klines.length > 0) return toTime(klines[klines.length - 1].timestamp)
    return 0 as Time
  }, [])

  const initChart = useCallback(() => {
    if (!containerRef.current || chartRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: '#555570', attributionLogo: false },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: C.border },
      timeScale: { borderColor: C.border, timeVisible: true },
      width: containerRef.current.clientWidth,
      height: showMACD ? height - 150 : height,
    })
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: C.up, downColor: C.down,
      borderDownColor: C.down, borderUpColor: C.up,
      wickDownColor: C.down, wickUpColor: C.up,
    })
    chartRef.current = chart
    candleRef.current = candle
    if (showVolume) {
      const vol = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      })
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
      overlaySeriesRef.current.push(vol)
    }

    // MACD sub-chart
    if (showMACD && macdContainerRef.current) {
      const macdChart = createChart(macdContainerRef.current, {
        layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: '#555570', attributionLogo: false },
        grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
        rightPriceScale: { borderColor: C.border },
        timeScale: { borderColor: C.border, timeVisible: true },
        width: macdContainerRef.current.clientWidth,
        height: 140,
      })
      macdChartRef.current = macdChart
    }
  }, [height, showVolume, showMACD])

  const drawOverlays = useCallback((result: AnalysisResult, klines: KLineData[]) => {
    const chart = chartRef.current
    const candle = candleRef.current
    if (!chart || !candle) return

    // Clear old overlay series (keep volume which is at index 0 if showVolume)
    const keepCount = showVolume ? 1 : 0
    overlaySeriesRef.current.slice(keepCount).forEach(s => {
      try { chart.removeSeries(s) } catch { /* ignore */ }
    })
    overlaySeriesRef.current = overlaySeriesRef.current.slice(0, keepCount)

    // STROKES — blue lines connecting fractal points
    if (layers.has('strokes') && result.strokes?.length) {
      const strokeSeries = chart.addSeries(LineSeries, {
        color: C.stroke,
        lineWidth: 1,
        priceScaleId: 'right',
        pointMarkersVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      })
      const pts: LineData<Time>[] = []
      for (const s of result.strokes) {
        pts.push({ time: toTime(s.start_time), value: +s.start_price })
        pts.push({ time: toTime(s.end_time), value: +s.end_price })
      }
      // Deduplicate and sort by time
      const uniquePts = deduplicateByTime(pts)
      if (uniquePts.length > 0) strokeSeries.setData(uniquePts)
      overlaySeriesRef.current.push(strokeSeries)
    }

    // SEGMENTS — purple thick lines
    if (layers.has('segments') && result.segments?.length) {
      const segSeries = chart.addSeries(LineSeries, {
        color: C.segment,
        lineWidth: 3,
        priceScaleId: 'right',
        pointMarkersVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
      })
      const pts: LineData<Time>[] = []
      for (const seg of result.segments) {
        const startPrice = seg.direction === 'up' ? +seg.low : +seg.high
        const endPrice = seg.direction === 'up' ? +seg.high : +seg.low
        pts.push({ time: toTime(seg.start_time), value: startPrice })
        pts.push({ time: toTime(seg.end_time), value: endPrice })
      }
      const uniquePts = deduplicateByTime(pts)
      if (uniquePts.length > 0) segSeries.setData(uniquePts)
      overlaySeriesRef.current.push(segSeries)
    }

    // SIGNALS — markers on candlestick
    if (layers.has('signals') && result.signals?.length) {
      const markers = result.signals.map(s => {
        const type = getSignalType(s)
        const buy = isBuySignal(s)
        return {
          time: toTime(s.timestamp),
          position: buy ? 'belowBar' as const : 'aboveBar' as const,
          color: buy ? C.buy : C.sell,
          shape: buy ? 'arrowUp' as const : 'arrowDown' as const,
          text: type,
        }
      }).sort((a, b) => (a.time as number) - (b.time as number))
      try { createSeriesMarkers(candle, markers) } catch { /* ignore */ }
    }

    // FRACTALS — markers
    if (layers.has('fractals') && result.fractals?.length) {
      // Use markers on candle series for fractals too
      const fractalMarkers = result.fractals.map(f => ({
        time: indexToTime(f.kline_index),
        position: f.type === 'top' ? 'aboveBar' as const : 'belowBar' as const,
        color: f.type === 'top' ? C.fractal_top : C.fractal_bottom,
        shape: f.type === 'top' ? 'circle' as const : 'circle' as const,
        text: f.type === 'top' ? '▽' : '△',
      })).sort((a, b) => (a.time as number) - (b.time as number))
      // Note: if signals already set markers, this will override. We combine.
      if (layers.has('signals') && result.signals?.length) {
        const signalMarkers = result.signals.map(s => {
          const type = getSignalType(s)
          const buy = isBuySignal(s)
          return {
            time: toTime(s.timestamp),
            position: buy ? 'belowBar' as const : 'aboveBar' as const,
            color: buy ? C.buy : C.sell,
            shape: buy ? 'arrowUp' as const : 'arrowDown' as const,
            text: type,
          }
        })
        const all = [...fractalMarkers, ...signalMarkers].sort((a, b) => (a.time as number) - (b.time as number))
        try { createSeriesMarkers(candle, all) } catch { /* ignore */ }
      } else {
        try { createSeriesMarkers(candle, fractalMarkers) } catch { /* ignore */ }
      }
    }

    // CENTERS — horizontal lines for ZG/ZD boundaries
    if (layers.has('centers') && result.centers?.length) {
      for (const c of result.centers) {
        // ZG line (upper)
        const zgLine = chart.addSeries(LineSeries, {
          color: C.center_border,
          lineWidth: 1,
          lineStyle: 2, // dashed
          priceScaleId: 'right',
          lastValueVisible: false,
          priceLineVisible: false,
          pointMarkersVisible: false,
        })
        const startT = c.start_time ? toTime(c.start_time) : indexToTime(0)
        const endT = c.end_time ? toTime(c.end_time) : indexToTime(klines.length - 1)
        zgLine.setData([
          { time: startT, value: +c.zg },
          { time: endT, value: +c.zg },
        ])
        overlaySeriesRef.current.push(zgLine)

        // ZD line (lower)
        const zdLine = chart.addSeries(LineSeries, {
          color: C.center_border,
          lineWidth: 1,
          lineStyle: 2,
          priceScaleId: 'right',
          lastValueVisible: false,
          priceLineVisible: false,
          pointMarkersVisible: false,
        })
        zdLine.setData([
          { time: startT, value: +c.zd },
          { time: endT, value: +c.zd },
        ])
        overlaySeriesRef.current.push(zdLine)
      }
    }

    // MACD chart
    if (showMACD && macdChartRef.current && result.macd_values?.length) {
      drawMACDChart(result, klines)
    }
  }, [layers, showVolume, showMACD, indexToTime])

  const drawMACDChart = (result: AnalysisResult, klines: KLineData[]) => {
    const macdChart = macdChartRef.current
    if (!macdChart || !result.macd_values?.length) return

    // Histogram
    const histSeries = macdChart.addSeries(HistogramSeries, {
      priceScaleId: 'right',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    const histData: HistogramData<Time>[] = result.macd_values.map((m, i) => {
      const val = +m.histogram
      return {
        time: (i < klines.length ? toTime(klines[i].timestamp) : (i as unknown as Time)),
        value: val,
        color: val >= 0 ? C.macd_pos : C.macd_neg,
      }
    })
    histSeries.setData(histData)

    // DIF line
    const difSeries = macdChart.addSeries(LineSeries, {
      color: C.dif,
      lineWidth: 1,
      priceScaleId: 'right',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    const difData: LineData<Time>[] = result.macd_values.map((m, i) => ({
      time: (i < klines.length ? toTime(klines[i].timestamp) : (i as unknown as Time)),
      value: +m.dif,
    }))
    difSeries.setData(difData)

    // DEA line
    const deaSeries = macdChart.addSeries(LineSeries, {
      color: C.dea,
      lineWidth: 1,
      priceScaleId: 'right',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    const deaData: LineData<Time>[] = result.macd_values.map((m, i) => ({
      time: (i < klines.length ? toTime(klines[i].timestamp) : (i as unknown as Time)),
      value: +m.dea,
    }))
    deaSeries.setData(deaData)

    macdChart.timeScale().fitContent()

    // Sync time scales
    if (chartRef.current) {
      chartRef.current.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) macdChart.timeScale().setVisibleLogicalRange(range)
      })
      macdChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) chartRef.current?.timeScale().setVisibleLogicalRange(range)
      })
    }
  }

  const loadData = useCallback(async () => {
    if (!candleRef.current) return
    setLoading(true)
    setError('')
    try {
      const klines = await getKLines(instrument, timeframe, limit)
      if (!klines.length) { setError('No data'); return }
      klineDataRef.current = klines

      const candles: CandlestickData<Time>[] = klines.map(k => ({
        time: toTime(k.timestamp),
        open: +k.open, high: +k.high, low: +k.low, close: +k.close,
      }))
      candleRef.current.setData(candles)

      // Volume
      if (showVolume && overlaySeriesRef.current[0]) {
        const vols: HistogramData<Time>[] = klines.map(k => ({
          time: toTime(k.timestamp),
          value: k.volume,
          color: +k.close >= +k.open ? C.vol_up : C.vol_down,
        }))
        overlaySeriesRef.current[0].setData(vols)
      }

      chartRef.current?.timeScale().fitContent()

      // Analyze
      try {
        const result = await analyzeInstrument(instrument, timeframe, klines)
        setAnalysis(result)
        onAnalysisComplete?.(result)
        drawOverlays(result, klines)
      } catch {
        // Analysis optional
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [instrument, timeframe, limit, showVolume, onAnalysisComplete, drawOverlays])

  // Redraw overlays when layers change
  useEffect(() => {
    if (analysis && klineDataRef.current.length) {
      drawOverlays(analysis, klineDataRef.current)
    }
  }, [layers, analysis, drawOverlays])

  // Resize
  useEffect(() => {
    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
      if (macdChartRef.current && macdContainerRef.current) {
        macdChartRef.current.applyOptions({ width: macdContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Init + load
  useEffect(() => {
    initChart()
    loadData()
    return () => {
      chartRef.current?.remove(); chartRef.current = null; candleRef.current = null
      macdChartRef.current?.remove(); macdChartRef.current = null
      overlaySeriesRef.current = []
    }
  }, [instrument, timeframe])

  // Hover tooltip
  useEffect(() => {
    if (!chartRef.current || !analysis) return
    const chart = chartRef.current
    const handler = (param: any) => {
      if (!param.point || !param.time) { setHoverInfo(null); return }
      const time = param.time as number
      // Find if hovering near a center
      if (analysis.centers?.length) {
        for (const c of analysis.centers) {
          const st = Math.floor(new Date(c.start_time).getTime() / 1000)
          const et = Math.floor(new Date(c.end_time).getTime() / 1000)
          if (time >= st && time <= et) {
            setHoverInfo(`Center: ZG=${(+c.zg).toFixed(2)} ZD=${(+c.zd).toFixed(2)} GG=${(+c.gg).toFixed(2)} DD=${(+c.dd).toFixed(2)} ext=${c.extension_count}`)
            return
          }
        }
      }
      setHoverInfo(null)
    }
    chart.subscribeCrosshairMove(handler)
    return () => { chart.unsubscribeCrosshairMove(handler) }
  }, [analysis])

  const walkLabel = analysis?.trend?.walk_state
  const walkColor = walkLabel === 'up_trend' ? 'text-accent-green' :
    walkLabel === 'down_trend' ? 'text-accent-red' :
    walkLabel === 'top_divergence' ? 'text-accent-red animate-pulse' :
    walkLabel === 'bottom_divergence' ? 'text-accent-green animate-pulse' :
    walkLabel === 'c_extending' ? 'text-accent-yellow animate-blink' :
    'text-accent-yellow'

  return (
    <div className={cn('relative', className)}>
      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10 bg-bg-primary/60">
          <div className="flex items-center gap-2 text-accent-cyan text-[11px] tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
            LOADING...
          </div>
        </div>
      )}
      {error && <div className="absolute top-2 left-2 z-10 tag tag-red">{error}</div>}

      {/* Top info bar */}
      {analysis && (
        <div className="absolute top-2 right-2 z-10 flex gap-1.5 flex-wrap justify-end">
          {walkLabel && (
            <span className={cn('tag font-semibold', walkColor)}>
              {walkLabel.replace('_', ' ').toUpperCase()}
            </span>
          )}
          <span className="tag tag-cyan">{analysis.kline_count}K</span>
          {analysis.stroke_count > 0 && (
            <span className="tag" style={{ borderColor: C.stroke + '60', color: C.stroke }}>
              {analysis.stroke_count}S
            </span>
          )}
          {analysis.segment_count > 0 && <span className="tag tag-purple">{analysis.segment_count}seg</span>}
          {analysis.center_count > 0 && <span className="tag tag-yellow">{analysis.center_count}C</span>}
          {analysis.divergence_count > 0 && <span className="tag tag-red">{analysis.divergence_count}div</span>}
          {analysis.signals.map((s, i) => {
            const type = getSignalType(s)
            return <span key={i} className={cn('tag font-semibold', isBuySignal(s) ? 'tag-green' : 'tag-red')}>{type}</span>
          })}
        </div>
      )}

      {/* Hover tooltip */}
      {hoverInfo && (
        <div className="absolute bottom-14 left-2 z-10 px-2 py-1 bg-bg-card/90 border border-bg-border rounded text-[10px] text-accent-yellow">
          {hoverInfo}
        </div>
      )}

      {/* Layer toggles */}
      {!compact && analysis && (
        <div className="absolute top-2 left-2 z-10 flex gap-1 flex-wrap">
          {ALL_LAYERS.map(l => (
            <button
              key={l.key}
              onClick={() => toggleLayer(l.key)}
              className={cn(
                'text-[9px] px-1.5 py-0.5 rounded border transition-all',
                layers.has(l.key)
                  ? 'border-current bg-current/10'
                  : 'border-bg-border text-text-muted opacity-50'
              )}
              style={layers.has(l.key) ? { color: l.color, borderColor: l.color + '60' } : undefined}
            >
              {l.label}
            </button>
          ))}
        </div>
      )}

      {/* Main chart */}
      <div ref={containerRef} style={{ height: showMACD ? height - 150 : height }} />

      {/* MACD sub-chart */}
      {showMACD && (
        <div className="border-t border-bg-border">
          <div className="px-2 py-1 text-[9px] text-text-muted flex items-center justify-between">
            <span>MACD (12,26,9)</span>
            {analysis?.divergences?.length ? (
              <span className="text-accent-red">
                {analysis.divergences.map((d, i) => (
                  <span key={i} className="ml-2">
                    {d.type.toUpperCase()} a={(+d.a_macd_area).toFixed(1)} c={(+d.c_macd_area).toFixed(1)} ({((+d.area_ratio) * 100).toFixed(1)}%)
                  </span>
                ))}
              </span>
            ) : null}
          </div>
          <div ref={macdContainerRef} style={{ height: 120 }} />
        </div>
      )}
    </div>
  )
}

/** Deduplicate line data points by time, keeping last value for each timestamp */
function deduplicateByTime(pts: LineData<Time>[]): LineData<Time>[] {
  const map = new Map<number, LineData<Time>>()
  for (const p of pts) map.set(p.time as number, p)
  return Array.from(map.values()).sort((a, b) => (a.time as number) - (b.time as number))
}
