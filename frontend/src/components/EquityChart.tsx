import { useEffect, useRef } from 'react'
import { AreaSeries, ColorType, LineSeries, createChart, type Time } from 'lightweight-charts'
import type { BacktestResult } from '../api'

export function EquityChart({ result, theme }: { result: BacktestResult; theme: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
    const grid = css('--border'), text = css('--muted'), accent = css('--accent'), down = css('--down'), flat = css('--neutral')
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: text, fontSize: 12, panes: { separatorColor: grid } },
      grid: { vertLines: { color: grid + '55' }, horzLines: { color: grid + '55' } },
      rightPriceScale: { borderColor: grid }, timeScale: { borderColor: grid },
    })
    const mk = (vals: number[]) => result.curve.dates.map((d, i) => ({ time: d as Time, value: vals[i] }))
    chart.addSeries(LineSeries, { color: flat, lineWidth: 1, lineStyle: 2, priceLineVisible: false, title: 'Comprar y mantener' }).setData(mk(result.curve.benchmark))
    chart.addSeries(LineSeries, { color: accent, lineWidth: 2, priceLineVisible: false, title: 'Estrategia' }).setData(mk(result.curve.equity))
    chart.addSeries(AreaSeries, { lineColor: down, topColor: down + '00', bottomColor: down + '55', lineWidth: 1, priceLineVisible: false, title: 'Drawdown' }, 1).setData(mk(result.curve.drawdown))
    try { const p = chart.panes(); p[0].setStretchFactor(3); p[1].setStretchFactor(1) } catch { /* sin paneles */ }
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [result, theme])
  return <div ref={ref} className="w-full h-[420px]" role="img" aria-label="Curva de capital y drawdown del backtest" />
}
