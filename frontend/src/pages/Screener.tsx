import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../hooks'
import { fmtNum, fmtPct, fmtPrice, toneClass } from '../format'
import { ErrorBox, Loading, Pill, Section, SyntheticBanner } from '../components/ui'

const CATS: [string, string][] = [['', 'Todas'], ['stock', 'Acciones'], ['etf', 'ETF'], ['crypto', 'Cripto'], ['forex', 'Forex'], ['commodity', 'Materias primas'], ['index', 'Índices']]
const DIRS: [string, string][] = [['', 'Cualquiera'], ['ALCISTA', 'Alcista'], ['NEUTRAL', 'Neutral'], ['BAJISTA', 'Bajista']]

export default function Screener() {
  const [cat, setCat] = useState('')
  const [dir, setDir] = useState('')
  const r = useAsync(() => api.screener(cat || undefined, dir || undefined), [cat, dir])
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Buscador de oportunidades</h1>
      <p className="text-sm text-muted">Ordena el catálogo por puntuación técnica. Es una foto del estado técnico reciente, no una predicción ni una recomendación.</p>
      <div className="flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2">Categoría
          <select className="input" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Categoría">{CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="flex items-center gap-2">Señal
          <select className="input" value={dir} onChange={(e) => setDir(e.target.value)} aria-label="Señal">{DIRS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {r.loading && !r.data ? <Loading label="Analizando el catálogo…" /> : r.error ? <ErrorBox message={r.error} onRetry={r.reload} /> : (
        <>
          <SyntheticBanner show={r.data!.any_synthetic} />
          <Section title={`Resultados (${r.data!.rows.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm num">
                <thead><tr className="text-left text-muted text-xs"><th className="py-1 pr-3">Activo</th><th>Señal</th><th>Punt.</th><th>Precio</th><th>Día</th><th>1M</th><th>3M</th><th>RSI</th><th>Vol.</th><th>vs SMA200</th><th>Dato</th></tr></thead>
                <tbody>
                  {r.data!.rows.map((x) => (
                    <tr key={x.symbol} className="border-t border-line">
                      <td className="py-1 pr-3"><Link className="text-accent underline" to={`/activo/${x.symbol}`}>{x.symbol}</Link> <span className="text-muted text-xs">{x.name}</span></td>
                      <td><Pill tone={x.direction === 'ALCISTA' ? 'up' : x.direction === 'BAJISTA' ? 'down' : 'flat'}>{x.direction.toLowerCase()}</Pill></td>
                      <td>{fmtNum(x.score, 2)}</td><td>{fmtPrice(x.price)}</td>
                      <td className={toneClass(x.change_pct)}>{fmtPct(x.change_pct)}</td>
                      <td className={toneClass(x.ret_1m)}>{fmtPct(x.ret_1m, 1)}</td><td className={toneClass(x.ret_3m)}>{fmtPct(x.ret_3m, 1)}</td>
                      <td>{fmtNum(x.rsi14, 0)}</td><td>{fmtPct(x.vol_annualized, 0, false)}</td><td className={toneClass(x.dist_sma200)}>{fmtPct(x.dist_sma200, 1)}</td>
                      <td><Pill tone={x.data_status === 'synthetic' ? 'warn' : 'flat'} title={x.provider}>{x.data_status_label}</Pill></td>
                    </tr>))}
                </tbody>
              </table>
            </div>
            {r.data!.rows.length === 0 && <p className="text-sm text-muted">Ningún activo cumple el filtro.</p>}
            {r.data!.missing.length > 0 && <p className="text-xs text-muted mt-2">Sin datos suficientes: {r.data!.missing.join(', ')}.</p>}
            <p className="text-[11px] text-muted mt-3">{r.data!.method}</p>
          </Section>
        </>)}
    </div>
  )
}
