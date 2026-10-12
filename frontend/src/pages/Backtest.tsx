import { useState, type FormEvent } from 'react'
import { api, type BacktestMetrics, type BacktestResult } from '../api'
import { useAsync } from '../hooks'
import { fmtNum, fmtPct, fmtPrice, toneClass } from '../format'
import { ErrorBox, Kv, Loading, Pill, Section } from '../components/ui'
import { EquityChart } from '../components/EquityChart'

const PARAM_LABELS: Record<string, string> = { fast: 'SMA rápida', slow: 'SMA lenta', period: 'Periodo RSI', buy_below: 'Comprar si RSI <', sell_above: 'Vender si RSI >', lookback: 'Ventana (barras)' }

function MetricsTable({ m, b }: { m: BacktestMetrics; b: BacktestMetrics }) {
  const rows: [string, (x: BacktestMetrics) => string][] = [
    ['Rentabilidad total', (x) => fmtPct(x.total_return)], ['Anualizada (CAGR)', (x) => fmtPct(x.cagr)], ['Volatilidad', (x) => fmtPct(x.volatility, 1, false)],
    ['Drawdown máximo', (x) => fmtPct(x.max_drawdown, 1, false)], ['Sharpe (rf = 0)', (x) => fmtNum(x.sharpe_rf0)],
  ]
  return (
    <table className="t"><thead><tr><th>Métrica</th><th className="text-right">Estrategia</th><th className="text-right">Comprar y mantener</th></tr></thead>
      <tbody>{rows.map(([k, f]) => <tr key={k}><td className="text-muted">{k}</td><td className="num text-right">{f(m)}</td><td className="num text-right">{f(b)}</td></tr>)}</tbody></table>
  )
}

export default function Backtest() {
  const strategies = useAsync(() => api.strategies(), [])
  const [form, setForm] = useState({ symbol: 'SPY', strategy: 'sma_cross', capital: '10000', commission: '', slippage: '', start: '', end: '', oos: '30' })
  const [params, setParams] = useState<Record<string, string>>({})
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const theme = document.documentElement.getAttribute('data-theme') ?? 'dark'

  if (strategies.loading && !strategies.data) return <Loading />
  if (strategies.error) return <ErrorBox message={strategies.error} onRetry={strategies.reload} />
  const strat = strategies.data!.strategies.find((s) => s.id === form.strategy)!

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    const p: Record<string, number> = {}
    for (const k of Object.keys(strat.params)) if (params[k] !== undefined && params[k] !== '') p[k] = Number(params[k])
    const body: Record<string, unknown> = { symbol: form.symbol, strategy: form.strategy, params: p, initial_capital: Number(form.capital) }
    if (form.commission !== '') body.commission_bps = Number(form.commission)
    if (form.slippage !== '') body.slippage_bps = Number(form.slippage)
    if (form.start) body.start = form.start
    if (form.end) body.end = form.end
    if (form.oos) body.oos_fraction = Number(form.oos) / 100
    api.backtest(body).then(setResult).catch((x: Error) => { setResult(null); setError(x.message) }).finally(() => setBusy(false))
  }
  const exportCsv = () => {
    if (!result) return
    const rows = ['entrada,precio_entrada,salida,precio_salida,cantidad,comisiones,pnl,retorno,cerrada', ...result.trades.map((t) => [t.entry_date, t.entry_price, t.exit_date, t.exit_price, t.qty, t.fees, t.pnl, t.return, t.closed].join(','))]
    const url = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' }))
    const a = document.createElement('a'); a.href = url; a.download = `backtest-${result.symbol}-${result.strategy}.csv`; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Backtesting</h1>
      <p className="text-sm text-muted">Las señales se calculan al cierre y las órdenes se ejecutan en la apertura de la barra siguiente, con comisión y slippage. Los parámetros son los que tú fijas: el motor no los optimiza.</p>
      <div className="grid lg:grid-cols-4 gap-4">
        <Section title="Configuración" className="lg:col-span-1">
          <form onSubmit={submit} className="space-y-2 text-xs text-muted">
            <label className="block">Símbolo<input className="input mt-1" required value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} /></label>
            <label className="block">Estrategia<select className="input mt-1" value={form.strategy} onChange={(e) => { setForm({ ...form, strategy: e.target.value }); setParams({}) }}>
              {strategies.data!.strategies.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
            {Object.entries(strat.params).map(([k, def]) => (
              <label key={k} className="block">{PARAM_LABELS[k] ?? k}<input className="input mt-1" inputMode="decimal" placeholder={String(def)} value={params[k] ?? ''} onChange={(e) => setParams({ ...params, [k]: e.target.value })} /></label>))}
            <label className="block">Capital inicial<input className="input mt-1" required inputMode="decimal" value={form.capital} onChange={(e) => setForm({ ...form, capital: e.target.value })} /></label>
            <div className="grid grid-cols-2 gap-2">
              <label>Comisión (pb)<input className="input mt-1" inputMode="decimal" placeholder="por defecto" value={form.commission} onChange={(e) => setForm({ ...form, commission: e.target.value })} /></label>
              <label>Slippage (pb)<input className="input mt-1" inputMode="decimal" placeholder="por defecto" value={form.slippage} onChange={(e) => setForm({ ...form, slippage: e.target.value })} /></label>
              <label>Desde<input type="date" className="input mt-1" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></label>
              <label>Hasta<input type="date" className="input mt-1" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></label>
            </div>
            <label className="block">% final reservado como fuera de muestra<input className="input mt-1" inputMode="numeric" value={form.oos} onChange={(e) => setForm({ ...form, oos: e.target.value })} /></label>
            <button className="btn btn-primary w-full" disabled={busy} type="submit">{busy ? 'Ejecutando…' : 'Ejecutar backtest'}</button>
          </form>
        </Section>
        <div className="lg:col-span-3 space-y-4">
          {error && <ErrorBox message={error} />}
          {!result && !error && <div className="card p-6 text-sm text-muted">Configura una estrategia y pulsa “Ejecutar backtest”.</div>}
          {result && (<>
            {result.warnings.map((w) => <div key={w} className={`card p-3 text-sm ${w.startsWith('ATENCIÓN') ? 'border-warn/60 text-warn' : 'text-muted'}`}>{w}</div>)}
            <Section title={`${result.label} · ${result.symbol}`} right={<span className="text-xs text-muted">{result.period.start} → {result.period.end} · {result.period.bars} barras</span>}>
              <EquityChart result={result} theme={theme} />
            </Section>
            <div className="grid md:grid-cols-2 gap-4">
              <Section title="Resultados"><MetricsTable m={result.metrics} b={result.benchmark} />
                <div className="mt-3"><Kv k="Capital final" v={fmtNum(result.final_equity)} /><Kv k="Operaciones" v={result.metrics.trades} /><Kv k="Aciertos" v={result.metrics.win_rate === null || result.metrics.win_rate === undefined ? '—' : fmtPct(result.metrics.win_rate, 0, false)} />
                  <Kv k="Exposición" v={fmtPct(result.metrics.exposure, 0, false)} /><Kv k="Comisiones pagadas" v={fmtNum(result.metrics.fees_paid)} />
                  <Kv k="Costes" v={`${result.costs.commission_bps} pb + ${result.costs.slippage_bps} pb`} /></div></Section>
              {result.segments && <Section title="Dentro / fuera de muestra" right={<Pill tone="accent">corte {result.segments.split_date}</Pill>}>
                <table className="t"><thead><tr><th /><th className="text-right">Primer tramo</th><th className="text-right">Tramo final</th></tr></thead><tbody>
                  <tr><td className="text-muted">Rentabilidad</td><td className="num text-right">{fmtPct(result.segments.in_sample.total_return)}</td><td className="num text-right">{fmtPct(result.segments.out_of_sample.total_return)}</td></tr>
                  <tr><td className="text-muted">Drawdown máx.</td><td className="num text-right">{fmtPct(result.segments.in_sample.max_drawdown, 1, false)}</td><td className="num text-right">{fmtPct(result.segments.out_of_sample.max_drawdown, 1, false)}</td></tr>
                  <tr><td className="text-muted">Sharpe</td><td className="num text-right">{fmtNum(result.segments.in_sample.sharpe_rf0)}</td><td className="num text-right">{fmtNum(result.segments.out_of_sample.sharpe_rf0)}</td></tr></tbody></table>
                <p className="text-[11px] text-muted mt-2">{result.segments.note}</p></Section>}
            </div>
            <Section title="Operaciones" right={<button className="btn" onClick={exportCsv}>Exportar CSV</button>}>
              {result.trades.length === 0 ? <p className="text-sm text-muted">La estrategia no generó operaciones en este periodo.</p> : (
                <div className="overflow-x-auto max-h-80 overflow-y-auto"><table className="t"><thead><tr><th>Entrada</th><th className="text-right">Precio</th><th>Salida</th><th className="text-right">Precio</th><th className="text-right">P/L</th><th className="text-right">Retorno</th><th /></tr></thead>
                  <tbody>{result.trades.map((t, i) => <tr key={i}><td>{t.entry_date}</td><td className="num text-right">{fmtPrice(t.entry_price)}</td><td>{t.exit_date}</td><td className="num text-right">{fmtPrice(t.exit_price)}</td>
                    <td className={`num text-right ${toneClass(t.pnl)}`}>{fmtNum(t.pnl)}</td><td className={`num text-right ${toneClass(t.return)}`}>{fmtPct(t.return)}</td><td className="text-xs text-muted">{t.closed ? '' : 'abierta'}</td></tr>)}</tbody></table></div>)}
            </Section>
          </>)}
          {busy && <Loading label="Ejecutando simulación…" />}
        </div>
      </div>
    </div>
  )
}
