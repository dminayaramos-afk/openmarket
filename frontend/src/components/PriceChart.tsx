import { useEffect, useRef } from 'react'
import {
  CandlestickSeries, ColorType, HistogramSeries, LineSeries, createChart, type Time,
} from 'lightweight-charts'
import type { ChartData, LinePoint } from '../api'

export interface ChartOptions { sma20: boolean; sma50: boolean; sma200: boolean; bb: boolean; volume: boolean; rsi: boolean; macd: boolean }

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()
const pts = (a: LinePoint[]) => a.map((p) => ({ time: p.time as Time, value: p.value }))

export function PriceChart({ data, opts, theme }: { data: ChartData; opts: ChartOptions; theme: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const text = css('--muted'), grid = css('--border'), up = css('--up'), down = css('--down'), accent = css('--accent'), warn = css('--warn')
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: text, fontSize: 12, panes: { separatorColor: grid } },
      grid: { vertLines: { color: grid + '55' }, horzLines: { color: grid + '55' } },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, timeVisible: false },
      crosshair: { mode: 0 },
    })
    const candles = chart.addSeries(CandlestickSeries, { upColor: up, downColor: down, borderVisible: false, wickUpColor: up, wickDownColor: down })
    candles.setData(data.candles.map((c) => ({ ...c, time: c.time as Time })))
    const line = (arr: LinePoint[], color: string, width = 1, style = 0) => {
      const s = chart.addSeries(LineSeries, { color, lineWidth: width as 1, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      s.setData(pts(arr))
    }
    if (opts.sma20) line(data.overlays.sma20, '#38bdf8')
    if (opts.sma50) line(data.overlays.sma50, warn)
    if (opts.sma200) line(data.overlays.sma200, '#c084fc', 2)
    if (opts.bb) { line(data.overlays.bb_upper, accent, 1, 2); line(data.overlays.bb_lower, accent, 1, 2) }
    if (opts.volume && data.volume.length) {
      const v = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'vol', priceLineVisible: false, lastValueVisible: false })
      v.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      v.setData(data.volume.map((x) => ({ time: x.time as Time, value: x.value, color: (x.up ? up : down) + '66' })))
    }
    let pane = 1
    if (opts.rsi) {
      const r = chart.addSeries(LineSeries, { color: '#38bdf8', lineWidth: 1, priceLineVisible: false }, pane)
      r.setData(pts(data.rsi))
      r.createPriceLine({ price: 70, color: down + '99', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '70' })
      r.createPriceLine({ price: 30, color: up + '99', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '30' })
      pane++
    }
    if (opts.macd) {
      const h = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane)
      h.setData(data.macd_hist.map((x) => ({ time: x.time as Time, value: x.value, color: (x.value >= 0 ? up : down) + '99' })))
      const m = chart.addSeries(LineSeries, { color: accent, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane)
      m.setData(pts(data.macd))
      const s = chart.addSeries(LineSeries, { color: warn, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane)
      s.setData(pts(data.macd_signal))
    }
    try {
      const panes = chart.panes()
      panes[0]?.setStretchFactor(3)
      for (let i = 1; i < panes.length; i++) panes[i].setStretchFactor(1)
    } catch { /* versión sin paneles ajustables */ }
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [data, opts, theme])

  return <div ref={ref} className="w-full h-[520px]" role="img" aria-label={`Gráfico de velas de ${data.symbol}`} />
}
