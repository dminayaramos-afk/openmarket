import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type AssetInfo, type Provenance, type Quote } from '../api'
import { fmtDateTime, fmtPct, fmtPrice, heatColor, toneClass } from '../format'

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card border-down/50 p-4 text-sm">
      <p className="text-down font-medium">No se pudo cargar</p>
      <p className="text-muted mt-1">{message}</p>
      {onRetry && <button className="btn mt-3" onClick={onRetry}>Reintentar</button>}
    </div>
  )
}

export function Loading({ label = 'Cargando…' }: { label?: string }) {
  return <div className="text-muted text-sm p-6" role="status" aria-live="polite">{label}</div>
}

export function Section({ title, right, children, className = '' }: { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-4 fade-in min-w-0 ${className}`}>
      <div className="flex items-center justify-between mb-3 gap-3">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-muted">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  )
}

export function Pill({ tone, children, title }: { tone: 'up' | 'down' | 'flat' | 'warn' | 'accent'; children: ReactNode; title?: string }) {
  const map = { up: 'text-up border-up/40', down: 'text-down border-down/40', flat: 'text-flat border-line', warn: 'text-warn border-warn/50', accent: 'text-accent border-accent/40' }
  return <span title={title} className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${map[tone]}`}>{children}</span>
}

/** Estado del dato: nunca se oculta que un dato es sintético o retrasado. */
export function DataBadge({ prov }: { prov: Provenance }) {
  const tone = prov.status === 'synthetic' ? 'warn' : prov.status === 'realtime' ? 'up' : 'flat'
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Pill tone={tone} title={prov.note}>{prov.status_label}</Pill>
      <span className="text-xs text-muted">{prov.provider}{prov.as_of ? ` · ${new Date(prov.as_of).toLocaleDateString('es-ES', { timeZone: 'UTC' })}` : ''}</span>
    </span>
  )
}

export function SyntheticBanner({ show }: { show: boolean }) {
  if (!show) return null
  return (
    <div role="status" className="card border-warn/60 p-3 text-sm flex gap-3 items-start">
      <span className="text-warn font-semibold">Datos sintéticos</span>
      <span className="text-muted">
        No hay datos reales para estos activos (sin conexión, sin clave del proveedor o sin archivo CSV), así que se muestran datos generados artificialmente para probar la interfaz.
        <strong className="text-ink"> No son precios reales</strong>. Para usar datos reales: pon una clave de Stooq o guarda un CSV en <code>data/prices/</code> (ver <Link className="underline text-accent" to="/configuracion">Configuración → Fuentes de datos</Link>).
      </span>
    </div>
  )
}

export function Sparkline({ values, up }: { values: number[]; up?: boolean }) {
  if (values.length < 2) return null
  const w = 96, h = 28
  const min = Math.min(...values), max = Math.max(...values)
  const span = max - min || 1
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`).join(' ')
  const rising = up ?? values[values.length - 1] >= values[0]
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={rising ? 'var(--up)' : 'var(--down)'} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

export function QuoteCard({ q }: { q: Quote }) {
  return (
    <Link to={`/activo/${q.symbol}`} className="card p-3 block hover:border-accent transition-colors">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">{q.symbol}</span>
        {q.provenance.status === 'synthetic' && <Pill tone="warn" title="Dato sintético, no real">sint.</Pill>}
      </div>
      <div className="text-xs text-muted truncate">{q.name}</div>
      <div className="flex items-end justify-between mt-2">
        <div>
          <div className="num text-lg font-semibold">{fmtPrice(q.price)}</div>
          <div className={`num text-sm ${toneClass(q.change_pct)}`}>{fmtPct(q.change_pct)}</div>
        </div>
        <Sparkline values={q.spark} />
      </div>
    </Link>
  )
}

export function Heatmap({ quotes }: { quotes: Quote[] }) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-1.5" role="list">
      {quotes.map((q) => (
        <Link role="listitem" key={q.symbol} to={`/activo/${q.symbol}`} title={`${q.name}: ${fmtPct(q.change_pct)}`}
          className="rounded-lg p-2 text-center border border-line/60 hover:border-accent transition-colors"
          style={{ background: heatColor(q.change_pct) }}>
          <div className="text-xs font-semibold">{q.symbol}</div>
          <div className="num text-xs">{fmtPct(q.change_pct, 1)}</div>
        </Link>
      ))}
    </div>
  )
}

/** Escala universal BAJISTA — NEUTRAL — ALCISTA con marcador según la puntuación (−1…+1). */
export function SignalGauge({ score, direction }: { score: number; direction: string }) {
  const pos = Math.min(100, Math.max(0, ((score + 1) / 2) * 100))
  const color = direction === 'ALCISTA' ? 'text-up' : direction === 'BAJISTA' ? 'text-down' : 'text-flat'
  return (
    <div>
      <div className="relative h-3 rounded-full overflow-hidden flex" role="img" aria-label={`Señal ${direction}, puntuación ${score}`}>
        <div className="flex-[37.5] bg-down/70" /><div className="flex-[25] bg-flat/60" /><div className="flex-[37.5] bg-up/70" />
        <div className="absolute top-[-3px] h-[18px] w-1 rounded bg-ink shadow" style={{ left: `calc(${pos}% - 2px)` }} />
      </div>
      <div className="flex justify-between text-[11px] text-muted mt-1 tracking-wide"><span>BAJISTA</span><span>NEUTRAL</span><span>ALCISTA</span></div>
      <div className={`text-center font-semibold mt-1 ${color}`}>{direction}</div>
    </div>
  )
}

export function SearchBox() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<AssetInfo[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const nav = useNavigate()
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!q.trim()) { setResults([]); return }
    let alive = true
    const t = setTimeout(() => {
      api.search(q.trim()).then((r) => { if (alive) { setResults(r.results); setActive(0) } }).catch(() => { if (alive) setResults([]) })
    }, 180)
    return () => { alive = false; clearTimeout(t) }
  }, [q])

  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const go = (s: string) => { setOpen(false); setQ(''); nav(`/activo/${s}`) }
  return (
    <div ref={box} className="relative w-full max-w-md">
      <input className="input" placeholder="Buscar activo: AAPL, bitcoin, EURUSD, IBEX…" aria-label="Buscador universal" role="combobox"
        aria-expanded={open && results.length > 0} aria-controls="search-results" value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }} onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && results[active]) go(results[active].symbol)
          else if (e.key === 'Escape') setOpen(false)
        }} />
      {open && q.trim() && (
        <ul id="search-results" role="listbox" className="absolute z-30 mt-1 w-full card p-1 max-h-80 overflow-auto shadow-xl">
          {results.length === 0 && <li className="px-3 py-2 text-sm text-muted">Sin resultados en el catálogo</li>}
          {results.map((r, i) => (
            <li key={r.symbol} role="option" aria-selected={i === active}
              className={`px-3 py-2 rounded-lg cursor-pointer text-sm flex justify-between gap-3 ${i === active ? 'bg-panel2' : ''}`}
              onMouseEnter={() => setActive(i)} onMouseDown={() => go(r.symbol)}>
              <span><strong>{r.symbol}</strong> <span className="text-muted">{r.name}</span></span>
              <span className="text-xs text-muted">{r.category_label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function LastUpdate({ iso }: { iso: string | null | undefined }) {
  return <span className="text-xs text-muted">Última actualización: {fmtDateTime(iso)}</span>
}

export function Kv({ k, v, hint }: { k: string; v: ReactNode; hint?: string }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-line/60 last:border-0 text-sm" title={hint}>
      <span className="text-muted">{k}</span><span className="num text-right">{v}</span>
    </div>
  )
}
