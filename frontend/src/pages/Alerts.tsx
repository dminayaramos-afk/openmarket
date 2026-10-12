import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AlertCheck } from '../api'
import { useAsync } from '../hooks'
import { fmtDateTime, fmtNum } from '../format'
import { ErrorBox, Loading, Pill, Section } from '../components/ui'

export default function Alerts() {
  const list = useAsync(() => api.alerts(), [])
  const [symbol, setSymbol] = useState('BTC-USD')
  const [kind, setKind] = useState('price_above')
  const [threshold, setThreshold] = useState('')
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [last, setLast] = useState<AlertCheck | null>(null)

  const check = () => api.alertsCheck().then((r) => { setLast(r); list.reload() }).catch((e: Error) => setErr(e.message))
  // Se evalúan al abrir la pantalla y cada minuto mientras está abierta (no hay servicio en segundo plano)
  useEffect(() => { check(); const id = setInterval(check, 60_000); return () => clearInterval(id) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const create = () => {
    setErr(null); setMsg(null)
    const t = Number(threshold.replace(',', '.'))
    if (!threshold || Number.isNaN(t)) { setErr('Introduce un valor numérico'); return }
    api.alertCreate({ symbol: symbol.trim().toUpperCase(), kind, threshold: t, note }).then(() => { setMsg('Alerta creada'); setThreshold(''); setNote(''); list.reload(); check() }).catch((e: Error) => setErr(e.message))
  }
  const kinds = list.data?.kinds ?? {}

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Alertas</h1>
      <p className="text-sm text-muted">Se evalúan solo mientras esta pantalla (o la aplicación) está abierta; no hay servicio en segundo plano ni avisos fuera de aquí. Las alertas no se evalúan con datos sintéticos.</p>
      {last && last.triggered.length > 0 && (
        <div role="alert" className="card border-warn/60 p-3 text-sm">{last.triggered.map((t) => <p key={t.id}><strong className="text-warn">Alerta disparada:</strong> {t.message}</p>)}</div>)}
      <Section title="Nueva alerta">
        <div className="flex flex-wrap gap-2 items-end text-sm">
          <label className="grid gap-1">Símbolo<input className="input" aria-label="Símbolo" value={symbol} onChange={(e) => setSymbol(e.target.value)} /></label>
          <label className="grid gap-1">Condición<select className="input" aria-label="Condición" value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(kinds).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label className="grid gap-1">Valor<input className="input" aria-label="Valor" inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} /></label>
          <label className="grid gap-1">Nota<input className="input" aria-label="Nota" value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <button className="btn btn-primary" onClick={create}>Crear</button>
        </div>
        {err && <p role="alert" className="text-sm text-down mt-2">{err}</p>}
        {msg && <p role="status" className="text-sm text-up mt-2">{msg}</p>}
      </Section>
      <Section title="Mis alertas" right={<button className="btn" onClick={check}>Evaluar ahora</button>}>
        {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> : list.data!.alerts.length === 0 ? <p className="text-sm text-muted">Aún no hay alertas.</p> : (
          <ul className="divide-y divide-line text-sm">
            {list.data!.alerts.map((a) => (
              <li key={a.id} className="py-2 flex flex-wrap items-center gap-3">
                <Link className="text-accent underline" to={`/activo/${a.symbol}`}>{a.symbol}</Link>
                <span>{a.kind_label} <strong className="num">{fmtNum(a.threshold, 2)}</strong></span>
                {a.active ? <Pill tone="accent">activa</Pill> : <Pill tone="warn">disparada {fmtDateTime(a.triggered_at)}</Pill>}
                {a.last_value !== null && <span className="text-xs text-muted">último valor {fmtNum(a.last_value, 2)} ({a.last_source})</span>}
                {a.note && <span className="text-xs text-muted">{a.note}</span>}
                <span className="ml-auto flex gap-2">
                  {!a.active && <button className="btn" onClick={() => api.alertRearm(a.id).then(list.reload)}>Rearmar</button>}
                  <button className="btn" aria-label={`Borrar alerta ${a.id}`} onClick={() => api.alertDelete(a.id).then(list.reload)}>Borrar</button>
                </span>
              </li>))}
          </ul>)}
        {last && last.skipped.length > 0 && <p className="text-xs text-muted mt-3">No evaluadas: {last.skipped.map((s) => `${s.symbol} (${s.reason})`).join('; ')}.</p>}
      </Section>
    </div>
  )
}
