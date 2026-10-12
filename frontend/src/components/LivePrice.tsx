import { api } from '../api'
import { usePolling } from '../hooks'
import { fmtDateTime, fmtPct, fmtPrice, toneClass } from '../format'
import { Pill } from './ui'

/** Precio en vivo (se actualiza solo). Si no hay proveedor, lo dice y explica cómo activarlo; nunca inventa un valor. */
export function LivePrice({ symbol, enabled }: { symbol: string; enabled: boolean }) {
  const { data, error } = usePolling(() => api.live([symbol]), 10_000, [symbol])
  if (!enabled && !data) {
    return <p className="text-xs text-muted" data-testid="live-off">Sin precio en vivo para este activo: se muestra el último cierre diario. Para acciones de EE. UU. define <code>OPENMARKET_FINNHUB_KEY</code> (clave gratuita de Finnhub).</p>
  }
  const q = data?.quotes[symbol]
  const err = data?.errors[symbol] ?? error
  if (!q) return <p className="text-xs text-muted" data-testid="live-wait">{err ? `Precio en vivo no disponible: ${err}` : 'Consultando precio en vivo…'}</p>
  return (
    <div className="card p-3 text-sm flex flex-wrap items-center gap-x-6 gap-y-1" data-testid="live-box">
      <Pill tone="up" title={q.note}>{q.status_label}</Pill>
      <span className="num text-xl font-semibold">{fmtPrice(q.price)} <span className="text-xs text-muted">{q.currency}</span></span>
      <span className={`num ${toneClass(q.change_pct_today)}`}>{fmtPct(q.change_pct_today)} hoy</span>
      {q.bid !== null && q.ask !== null && <span className="text-xs text-muted num">oferta {fmtPrice(q.bid)} · demanda {fmtPrice(q.ask)}</span>}
      <span className="text-xs text-muted">{q.provider} · {fmtDateTime(q.as_of)}{err ? ` · último intento fallido: ${err}` : ''}</span>
    </div>
  )
}
