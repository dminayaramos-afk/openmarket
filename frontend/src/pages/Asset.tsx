import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type AssetDetail } from '../api'
import { useAsync } from '../hooks'
import { fmtDateTime, fmtNum, fmtPct, fmtPrice, toneClass } from '../format'
import { DataBadge, ErrorBox, Kv, Loading, Pill, Section, SignalGauge, SyntheticBanner } from '../components/ui'
import { PriceChart, type ChartOptions } from '../components/PriceChart'

const INDICATOR_LABELS: [string, string, 'price' | 'num' | 'pct'][] = [
  ['sma20', 'SMA 20', 'price'], ['sma50', 'SMA 50', 'price'], ['sma200', 'SMA 200', 'price'], ['ema12', 'EMA 12', 'price'], ['ema26', 'EMA 26', 'price'],
  ['rsi14', 'RSI (14)', 'num'], ['macd', 'MACD', 'num'], ['macd_signal', 'MACD señal', 'num'], ['macd_hist', 'MACD histograma', 'num'],
  ['bb_upper', 'Bollinger superior', 'price'], ['bb_lower', 'Bollinger inferior', 'price'], ['bb_pct_b', 'Bollinger %B', 'num'],
  ['atr14', 'ATR (14)', 'price'], ['adx14', 'ADX (14)', 'num'], ['momentum20', 'Momentum 20', 'pct'], ['vol20_annualized', 'Volatilidad 20 anualizada', 'pct'], ['vwap20', 'VWAP 20', 'price'],
]

function SignalPanel({ d }: { d: AssetDetail }) {
  const s = d.signal
  if (!s.available) {
    return <Section title="Señal alcista / neutral / bajista"><p className="text-sm text-warn">{s.reason}</p></Section>
  }
  const p = s.probabilities
  const v = s.validation
  return (
    <Section title="Señal alcista / neutral / bajista" right={<Pill tone="warn" title="Análisis informativo">no es asesoramiento</Pill>}>
      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <SignalGauge score={s.score!} direction={s.direction!} />
          <div className="mt-4 text-sm space-y-0.5">
            <Kv k="Puntuación técnica (−1…+1)" v={fmtNum(s.score, 2)} hint="Combinación de tendencia, momentum, MACD y RSI. NO es una probabilidad." />
            <Kv k="Intensidad" v={fmtNum(s.intensity, 2)} />
            <Kv k="Horizonte" v={s.horizon_text} />
            <Kv k="Incertidumbre" v={`${s.uncertainty_label} (${fmtNum(s.uncertainty, 2)})`} />
            <Kv k="Datos utilizados" v={s.data_used} />
            <Kv k="Calculado" v={fmtDateTime(s.computed_at)} />
          </div>
          <p className="text-sm text-muted mt-3">{s.explanation}</p>
          <p className="text-[11px] text-muted mt-2">Umbrales: bajista {s.thresholds?.bajista}; neutral {s.thresholds?.neutral}; alcista {s.thresholds?.alcista}.</p>
        </div>
        <div className="space-y-4 text-sm">
          {[['Factores favorables', s.favorable, 'text-up'], ['Factores desfavorables', s.unfavorable, 'text-down'], ['Riesgos', s.risks, 'text-warn']].map(([t, list, c]) => (
            <div key={t as string}><div className={`font-medium ${c as string}`}>{t as string}</div>
              {(list as string[]).length ? <ul className="list-disc ml-5 text-muted">{(list as string[]).map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">Ninguno destacado.</p>}</div>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-6 pt-4 border-t border-line">
        <div>
          <h3 className="font-medium text-sm mb-2">Probabilidades empíricas a {p?.horizon_bars ?? 20} barras</h3>
          {p?.available && p.probabilities ? (
            <>
              <div className="flex h-7 rounded-lg overflow-hidden text-xs font-medium num" role="img" aria-label={`Bajada ${p.probabilities.bajada} %, neutral ${p.probabilities.neutral} %, subida ${p.probabilities.subida} %`}>
                <div className="bg-down/70 flex items-center justify-center" style={{ width: `${p.probabilities.bajada}%` }}>{p.probabilities.bajada} %</div>
                <div className="bg-flat/60 flex items-center justify-center" style={{ width: `${p.probabilities.neutral}%` }}>{p.probabilities.neutral} %</div>
                <div className="bg-up/70 flex items-center justify-center" style={{ width: `${p.probabilities.subida}%` }}>{p.probabilities.subida} %</div>
              </div>
              <div className="flex justify-between text-[11px] text-muted mt-1"><span>bajada</span><span>neutral</span><span>subida</span></div>
              <p className="text-xs text-muted mt-2">{p.definition}</p>
              <p className="text-xs text-muted mt-1">{p.method} Muestra: {p.n_samples} observaciones (≈ {p.effective_samples} independientes). {p.caveat}</p>
            </>
          ) : <p className="text-sm text-warn">{p?.reason}</p>}
        </div>
        <div>
          <h3 className="font-medium text-sm mb-2">Validación fuera de muestra (walk-forward)</h3>
          {v?.available ? (
            <div className="text-sm">
              <Kv k="Evaluaciones" v={v.n_eval} /><Kv k="Brier del modelo" v={fmtNum(v.brier, 4)} /><Kv k="Brier de referencia" v={fmtNum(v.brier_baseline, 4)} />
              <Kv k="Log loss modelo / referencia" v={`${fmtNum(v.log_loss, 3)} / ${fmtNum(v.log_loss_baseline, 3)}`} />
              <Kv k="Mejora sobre la referencia" v={fmtPct(v.skill_vs_baseline, 1)} />
              <p className={`mt-2 text-xs ${(v.skill_vs_baseline ?? 0) > 0.01 ? 'text-up' : 'text-warn'}`}>{v.verdict}</p>
              <p className="text-[11px] text-muted mt-1">{v.note}</p>
            </div>
          ) : <p className="text-sm text-warn">{v?.reason}</p>}
        </div>
      </div>
      <p className="text-[11px] text-muted mt-4">{s.disclaimer}</p>
    </Section>
  )
}

export default function Asset() {
  const { symbol = '' } = useParams()
  const detail = useAsync(() => api.asset(symbol), [symbol])
  const chart = useAsync(() => api.chart(symbol), [symbol])
  const [theme, setTheme] = useState(document.documentElement.getAttribute('data-theme') ?? 'dark')
  const [fav, setFav] = useState(false)
  const [opts, setOpts] = useState<ChartOptions>({ sma20: false, sma50: true, sma200: true, bb: false, volume: true, rsi: true, macd: false })

  useEffect(() => {
    const obs = new MutationObserver(() => setTheme(document.documentElement.getAttribute('data-theme') ?? 'dark'))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])
  useEffect(() => { api.watchlist().then((w) => setFav(w.symbols.includes(symbol.toUpperCase()))).catch(() => undefined) }, [symbol])

  if (detail.loading && !detail.data) return <Loading label={`Analizando ${symbol}…`} />
  if (detail.error) return <ErrorBox message={detail.error} onRetry={detail.reload} />
  const d = detail.data!
  const q = d.quote
  const toggle = (k: keyof ChartOptions) => setOpts((o) => ({ ...o, [k]: !o[k] }))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">{d.asset.name} <span className="text-muted text-lg">{d.asset.symbol}</span></h1>
            <button className="btn" aria-pressed={fav} title={fav ? 'Quitar de favoritos' : 'Añadir a favoritos'}
              onClick={() => (fav ? api.watchRemove(d.asset.symbol) : api.watchAdd(d.asset.symbol)).then((w) => setFav(w.symbols.includes(d.asset.symbol)))}>{fav ? '★' : '☆'}</button>
          </div>
          <div className="text-sm text-muted">{d.asset.category_label} · {d.asset.market} · {d.asset.currency}</div>
        </div>
        <div className="text-right">
          <div className="num text-3xl font-semibold">{fmtPrice(q.price)} <span className="text-base text-muted">{d.asset.currency}</span></div>
          <div className={`num ${toneClass(q.change_pct)}`}>{fmtPrice(q.change)} ({fmtPct(q.change_pct)})</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <DataBadge prov={d.provenance} />
        <span className="text-xs text-muted">Obtenido: {fmtDateTime(d.provenance.fetched_at)} · {d.provenance.note}</span>
        <button className="btn" onClick={() => api.asset(symbol, true).then(() => { detail.reload(); chart.reload() })}>Refrescar desde el proveedor</button>
      </div>
      <SyntheticBanner show={d.provenance.status === 'synthetic'} />
      {d.provenance.warnings.filter((w) => !w.toLowerCase().includes('sintético')).length > 0 && (
        <div className="card border-warn/60 p-3 text-xs text-muted"><strong className="text-warn">Avisos de la fuente:</strong> {d.provenance.warnings.filter((w) => !w.toLowerCase().includes('sintético')).join(' · ')}</div>
      )}
      {d.asset.note && <p className="text-sm text-muted">{d.asset.note}</p>}

      <Section title="Gráfico" right={
        <div className="flex flex-wrap gap-1.5 text-xs">
          {([['sma20', 'SMA20'], ['sma50', 'SMA50'], ['sma200', 'SMA200'], ['bb', 'Bollinger'], ['volume', 'Volumen'], ['rsi', 'RSI'], ['macd', 'MACD']] as [keyof ChartOptions, string][]).map(([k, label]) => (
            <button key={k} className={`btn ${opts[k] ? 'btn-primary' : ''}`} aria-pressed={opts[k]} onClick={() => toggle(k)}>{label}</button>))}
        </div>}>
        {chart.loading && !chart.data ? <Loading /> : chart.error ? <ErrorBox message={chart.error} onRetry={chart.reload} /> : chart.data && <PriceChart data={chart.data} opts={opts} theme={theme} />}
      </Section>

      <SignalPanel d={d} />

      <div className="grid md:grid-cols-3 gap-4">
        <Section title="Rendimiento por periodos">
          {Object.entries(d.returns).map(([k, v]) => <Kv key={k} k={k} v={<span className={toneClass(v)}>{fmtPct(v)}</span>} />)}
        </Section>
        <Section title="Riesgo histórico">
          {d.risk.available ? (<>
            <Kv k="Volatilidad anualizada" v={fmtPct(d.risk.annualized_volatility, 1, false)} />
            <Kv k="Drawdown máximo" v={<span className="text-down">{fmtPct(d.risk.max_drawdown, 1, false)}</span>} />
            <Kv k="Drawdown actual" v={fmtPct(d.risk.current_drawdown, 1, false)} />
            <Kv k="VaR 95 % (1 barra)" v={fmtPct(d.risk.var_95_1d, 2, false)} />
            <Kv k="CVaR 95 % (1 barra)" v={fmtPct(d.risk.cvar_95_1d, 2, false)} />
            <Kv k="Peor / mejor día" v={`${fmtPct(d.risk.worst_day, 1, false)} / ${fmtPct(d.risk.best_day, 1, false)}`} />
            <p className="text-[11px] text-muted mt-2">{d.risk.note}</p>
          </>) : <p className="text-sm text-warn">{d.risk.reason}</p>}
        </Section>
        <Section title="Soportes y resistencias (estimados)">
          <div className="text-sm">
            <div className="text-up font-medium">Soportes</div>{d.levels.support.length ? d.levels.support.map((x) => <div key={x} className="num">{fmtPrice(x)}</div>) : <div className="text-muted">—</div>}
            <div className="text-down font-medium mt-2">Resistencias</div>{d.levels.resistance.length ? d.levels.resistance.map((x) => <div key={x} className="num">{fmtPrice(x)}</div>) : <div className="text-muted">—</div>}
            <p className="text-[11px] text-muted mt-2">Pivotes confirmados agrupados por cercanía. Heurística: no garantiza rebotes.</p>
          </div>
        </Section>
      </div>

      <Section title="Indicadores técnicos (último valor)">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-8">
          {INDICATOR_LABELS.map(([k, label, kind]) => <Kv key={k} k={label} v={d.indicators[k] === null || d.indicators[k] === undefined ? '—' : kind === 'price' ? fmtPrice(d.indicators[k]) : kind === 'pct' ? fmtPct(d.indicators[k]) : fmtNum(d.indicators[k], 2)} />)}
        </div>
        {d.notes.map((n) => <p key={n} className="text-xs text-muted mt-2">{n}</p>)}
        <p className="text-xs text-muted mt-2">{d.bars} barras diarias ({d.first_date} → {d.last_date}).</p>
      </Section>
      <p className="text-xs text-muted">Información fundamental, noticias y comparación con referencias aún no están implementadas para esta ficha.</p>
    </div>
  )
}
