import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Quote } from '../api'
import { useAsync } from '../hooks'
import { fmtDate, fmtPct, fmtPrice, toneClass } from '../format'
import { DataBadge, ErrorBox, LastUpdate, Loading, Section, Sparkline, SyntheticBanner } from '../components/ui'

type SortKey = 'symbol' | 'name' | 'price' | 'change_pct' | 'as_of'

const TITLES: Record<string, string> = { stock: 'Acciones', etf: 'ETF y fondos', crypto: 'Criptomonedas', forex: 'Forex', commodity: 'Materias primas', index: 'Índices' }

function QuoteTable({ quotes }: { quotes: Quote[] }) {
  const [key, setKey] = useState<SortKey>('symbol')
  const [dir, setDir] = useState<1 | -1>(1)
  const sorted = useMemo(() => [...quotes].sort((a, b) => {
    const av = (a[key] ?? '') as string | number, bv = (b[key] ?? '') as string | number
    return (av < bv ? -1 : av > bv ? 1 : 0) * dir
  }), [quotes, key, dir])
  const th = (k: SortKey, label: string, right = false) => (
    <th className={right ? 'text-right' : ''} aria-sort={key === k ? (dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button className="hover:text-ink" onClick={() => { if (key === k) setDir((d) => (d === 1 ? -1 : 1)); else { setKey(k); setDir(1) } }}>
        {label}{key === k ? (dir === 1 ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  )
  return (
    <div className="overflow-x-auto">
      <table className="t">
        <thead><tr>{th('symbol', 'Símbolo')}{th('name', 'Nombre')}{th('price', 'Precio', true)}{th('change_pct', 'Var. diaria', true)}<th>Tendencia</th>{th('as_of', 'Fecha dato')}<th>Estado</th></tr></thead>
        <tbody>{sorted.map((q) => (
          <tr key={q.symbol}>
            <td><Link className="font-semibold hover:text-accent" to={`/activo/${q.symbol}`}>{q.symbol}</Link></td>
            <td className="text-muted">{q.name}</td>
            <td className="num text-right">{fmtPrice(q.price)} <span className="text-xs text-muted">{q.currency}</span></td>
            <td className={`num text-right ${toneClass(q.change_pct)}`}>{fmtPct(q.change_pct)}</td>
            <td><Sparkline values={q.spark} /></td>
            <td className="text-muted">{fmtDate(q.as_of)}</td>
            <td><DataBadge prov={q.provenance} /></td>
          </tr>))}</tbody>
      </table>
    </div>
  )
}

export function CategoryPage() {
  const { category = 'stock' } = useParams()
  const res = useAsync(() => api.quotes({ category }), [category])
  const title = TITLES[category] ?? category
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2"><h1 className="text-xl font-semibold">{title}</h1>{res.data && <LastUpdate iso={res.data.last_update} />}</div>
      {res.loading && !res.data ? <Loading /> : res.error ? <ErrorBox message={res.error} onRetry={res.reload} /> : res.data && (
        <>
          <SyntheticBanner show={res.data.any_synthetic} />
          {res.data.quotes[0]?.note && <p className="text-sm text-muted">{res.data.quotes[0].note}</p>}
          <Section title={`${res.data.quotes.length} instrumentos`}><QuoteTable quotes={res.data.quotes} /></Section>
        </>
      )}
    </div>
  )
}

export function GlobalMarkets() {
  const res = useAsync(async () => {
    const all = await api.assets()
    return api.quotes({ symbols: all.assets.map((a) => a.symbol) })
  }, [])
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2"><h1 className="text-xl font-semibold">Mercados globales</h1>{res.data && <LastUpdate iso={res.data.last_update} />}</div>
      {res.loading && !res.data ? <Loading label="Cargando todos los mercados…" /> : res.error ? <ErrorBox message={res.error} onRetry={res.reload} /> : res.data && (
        <>
          <SyntheticBanner show={res.data.any_synthetic} />
          {Object.entries(TITLES).map(([cat, title]) => {
            const rows = res.data!.quotes.filter((q) => q.category === cat)
            return rows.length ? <Section key={cat} title={title}><QuoteTable quotes={rows} /></Section> : null
          })}
          {Object.keys(res.data.errors).length > 0 && <p className="text-sm text-muted">Sin datos para: {Object.keys(res.data.errors).join(', ')}</p>}
        </>
      )}
    </div>
  )
}
