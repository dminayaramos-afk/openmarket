import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../hooks'
import { fmtPct, fmtPrice, toneClass } from '../format'
import { ErrorBox, Heatmap, LastUpdate, Loading, Pill, QuoteCard, Section, Sparkline, SyntheticBanner } from '../components/ui'

const INDEX_SYMBOLS = ['SPX', 'NDX', 'DJI', 'IBEX', 'DAX', 'FTSE', 'N225', 'HSI']
const CORR_SYMBOLS = ['SPX', 'NDX', 'IBEX', 'BTC-USD', 'XAUUSD', 'EURUSD']

function corrColor(v: number) {
  const k = Math.abs(v)
  return `color-mix(in srgb, ${v >= 0 ? 'var(--accent)' : 'var(--warn)'} ${Math.round(k * 70)}%, var(--panel-2))`
}

export default function Dashboard() {
  const quotes = useAsync(() => api.quotes(), [])
  const sources = useAsync(() => api.sources(), [])
  const corr = useAsync(() => api.correlations(CORR_SYMBOLS), [])
  const watch = useAsync(() => api.watchlist().then((w) => (w.symbols.length ? api.quotes({ symbols: w.symbols }) : { quotes: [], errors: {}, last_update: null, any_synthetic: false })), [])
  const pfs = useAsync(() => api.portfolios(), [])

  if (quotes.loading && !quotes.data) return <Loading label="Cargando mercados…" />
  if (quotes.error) return <ErrorBox message={quotes.error} onRetry={quotes.reload} />
  const q = quotes.data!
  const indices = INDEX_SYMBOLS.map((s) => q.quotes.find((x) => x.symbol === s)).filter(Boolean) as typeof q.quotes
  const movers = [...q.quotes].filter((x) => x.change_pct !== null).sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0))
  const gainers = movers.slice(0, 5)
  const losers = movers.slice(-5).reverse()
  const missing = Object.keys(q.errors)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <div className="flex items-center gap-3"><LastUpdate iso={q.last_update} /><button className="btn" onClick={quotes.reload}>Actualizar</button></div>
      </div>
      <SyntheticBanner show={q.any_synthetic} />
      {missing.length > 0 && <div className="card border-warn/60 p-3 text-sm text-muted">Sin datos para: {missing.join(', ')}.</div>}

      <Section title="Índices principales" right={<span className="text-xs text-muted">Los índices no se pueden comprar directamente</span>}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{indices.map((i) => <QuoteCard key={i.symbol} q={i} />)}</div>
      </Section>

      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Mapa de calor (variación diaria)" className="lg:col-span-2"><Heatmap quotes={q.quotes} /></Section>
        <Section title="Mayores subidas y bajadas">
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[['Suben', gainers], ['Bajan', losers]].map(([title, list]) => (
              <div key={title as string}>
                <div className="text-xs text-muted mb-1">{title as string}</div>
                {(list as typeof gainers).map((m) => (
                  <Link key={m.symbol} to={`/activo/${m.symbol}`} className="flex justify-between py-1 hover:text-accent">
                    <span>{m.symbol}</span><span className={`num ${toneClass(m.change_pct)}`}>{fmtPct(m.change_pct)}</span>
                  </Link>
                ))}
              </div>
            ))}
          </div>
        </Section>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Activos favoritos" right={<span className="text-xs text-muted">Añade con ☆ en la ficha</span>}>
          {watch.loading ? <Loading /> : watch.data && watch.data.quotes.length > 0 ? (
            <table className="t"><tbody>{watch.data.quotes.map((w) => (
              <tr key={w.symbol}><td><Link className="hover:text-accent" to={`/activo/${w.symbol}`}>{w.symbol}</Link></td>
                <td className="num text-right">{fmtPrice(w.price)}</td><td className={`num text-right ${toneClass(w.change_pct)}`}>{fmtPct(w.change_pct)}</td>
                <td><Sparkline values={w.spark} /></td></tr>))}</tbody></table>
          ) : <p className="text-sm text-muted">Todavía no tienes favoritos.</p>}
        </Section>

        <Section title="Correlaciones (retornos diarios)">
          {corr.loading ? <Loading /> : corr.data?.available ? (
            <>
              <div className="overflow-x-auto"><table className="text-xs num border-separate border-spacing-0.5">
                <thead><tr><th />{corr.data.symbols!.map((s) => <th key={s} className="px-1 text-muted font-normal">{s.replace('-USD', '')}</th>)}</tr></thead>
                <tbody>{corr.data.matrix!.map((row, i) => (
                  <tr key={i}><th className="pr-1 text-muted font-normal text-right">{corr.data!.symbols![i].replace('-USD', '')}</th>
                    {row.map((v, j) => <td key={j} className="text-center rounded px-1.5 py-1" style={{ background: corrColor(v) }}>{v.toFixed(2)}</td>)}</tr>))}</tbody>
              </table></div>
              <p className="text-[11px] text-muted mt-2">{corr.data.note} Fechas comunes: {corr.data.overlap}.</p>
            </>
          ) : <p className="text-sm text-muted">{corr.error ?? corr.data?.reason ?? 'No disponible'}</p>}
        </Section>

        <Section title="Resumen de cartera" right={<Link className="text-xs text-accent" to="/carteras">Gestionar</Link>}>
          {pfs.loading ? <Loading /> : pfs.data && pfs.data.portfolios.length > 0 ? (
            <ul className="space-y-1.5 text-sm">{pfs.data.portfolios.map((p) => (
              <li key={p.id}><Link className="hover:text-accent" to={`/carteras?id=${p.id}`}>{p.name}</Link>{' '}
                <span className="text-muted">({p.base_currency}){p.paper && ' · simulada'}</span></li>))}</ul>
          ) : <p className="text-sm text-muted">Aún no hay carteras. <Link className="text-accent" to="/carteras">Crea la primera</Link> (no necesitas bróker).</p>}
        </Section>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Estado de las fuentes de datos" className="lg:col-span-2">
          {sources.loading ? <Loading /> : sources.data ? (
            <table className="t"><thead><tr><th>Fuente</th><th>Estado</th><th>Aciertos</th><th>Errores</th><th>Último error</th></tr></thead>
              <tbody>{sources.data.sources.map((s) => (
                <tr key={s.name}><td>{s.label}</td>
                  <td>{!s.enabled ? <Pill tone="flat">desactivada</Pill> : s.name === 'synthetic' ? <Pill tone="warn">demostración</Pill> : s.error_count > 0 && s.ok_count === 0 ? <Pill tone="down">sin respuesta</Pill> : s.ok_count > 0 ? <Pill tone="up">operativa</Pill> : <Pill tone="flat">sin usar</Pill>}</td>
                  <td className="num">{s.ok_count}</td><td className="num">{s.error_count}</td>
                  <td className="text-xs text-muted max-w-xs truncate" title={s.last_error ?? ''}>{s.last_error ?? '—'}</td></tr>))}</tbody></table>
          ) : <ErrorBox message={sources.error ?? ''} />}
        </Section>
        <Section title="Noticias, calendario y macro">
          <p className="text-sm text-muted">Estas secciones <strong className="text-ink">aún no están implementadas</strong>: no hay una fuente verificable integrada. No se muestran datos inventados.</p>
        </Section>
      </div>
    </div>
  )
}
