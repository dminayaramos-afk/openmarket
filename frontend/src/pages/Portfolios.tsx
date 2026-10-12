import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type PortfolioSummary } from '../api'
import { useAsync } from '../hooks'
import { fmtDateTime, fmtNum, fmtPct, fmtPrice, toneClass } from '../format'
import { ErrorBox, Kv, Loading, Pill, Section } from '../components/ui'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs text-muted">{label}<div className="mt-1 text-ink">{children}</div></label>
}

function Detail({ id, onDeleted }: { id: number; onDeleted: () => void }) {
  const res = useAsync(() => api.portfolio(id), [id])
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [tx, setTx] = useState({ type: 'deposit', symbol: '', quantity: '', price: '', fee: '', amount: '' })
  const [order, setOrder] = useState({ symbol: '', side: 'buy', quantity: '' })

  if (res.loading && !res.data) return <Loading />
  if (res.error) return <ErrorBox message={res.error} onRetry={res.reload} />
  const s: PortfolioSummary = res.data!
  const paper = s.portfolio.paper
  const cur = s.portfolio.base_currency
  const run = (p: Promise<unknown>, okText: string) => p.then(() => { setMsg({ ok: true, text: okText }); res.reload() }).catch((e: Error) => setMsg({ ok: false, text: e.message }))
  const num = (v: string) => (v === '' ? undefined : Number(v.replace(',', '.')))

  const submitTx = (e: FormEvent) => {
    e.preventDefault()
    const body: Record<string, unknown> = { type: tx.type }
    if (tx.type === 'buy' || tx.type === 'sell') { Object.assign(body, { symbol: tx.symbol, quantity: num(tx.quantity), price: num(tx.price), fee: num(tx.fee) ?? 0 }) } else { body.amount = num(tx.amount) }
    run(api.portfolioTx(id, body), 'Transacción registrada')
  }
  const submitOrder = (e: FormEvent) => { e.preventDefault(); run(api.paperOrder(id, { symbol: order.symbol, side: order.side, quantity: num(order.quantity) }), 'Orden simulada ejecutada') }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{s.portfolio.name} {paper && <Pill tone="accent">paper trading</Pill>}</h2>
        <div className="flex gap-2">
          <a className="btn" href={`/api/portfolios/${id}/export.csv`} download>Exportar CSV</a>
          <button className="btn" onClick={() => { if (confirm('¿Eliminar esta cartera y todas sus transacciones?')) api.portfolioDelete(id).then(onDeleted) }}>Eliminar</button>
        </div>
      </div>
      {s.warnings.map((w) => <div key={w} className="card border-warn/60 p-3 text-sm text-muted">{w}</div>)}
      {msg && <div role="status" className={`card p-3 text-sm ${msg.ok ? 'border-up/50' : 'border-down/50 text-down'}`}>{msg.text}</div>}

      <div className="grid md:grid-cols-4 gap-3">
        {[['Valor total', `${fmtNum(s.total_value)} ${cur}`, ''], ['Efectivo', `${fmtNum(s.cash)} ${cur}`, ''],
          ['P/L no realizado', `${fmtNum(s.unrealized_pnl)} ${cur}`, toneClass(s.unrealized_pnl)], ['P/L realizado', `${fmtNum(s.realized_pnl)} ${cur}`, toneClass(s.realized_pnl)]].map(([k, v, c]) => (
          <div key={k} className="card p-3"><div className="text-xs text-muted">{k}</div><div className={`num text-lg font-semibold ${c}`}>{v}</div></div>))}
      </div>

      <Section title="Posiciones (coste medio ponderado)">
        {s.positions.length === 0 ? <p className="text-sm text-muted">Sin posiciones.</p> : (
          <div className="overflow-x-auto"><table className="t"><thead><tr><th>Activo</th><th className="text-right">Cantidad</th><th className="text-right">Coste medio</th><th className="text-right">Último</th><th className="text-right">Valor</th><th className="text-right">P/L</th><th className="text-right">Peso</th><th>Dato</th></tr></thead>
            <tbody>{s.positions.map((p) => (
              <tr key={p.symbol}><td><Link className="hover:text-accent font-semibold" to={`/activo/${p.symbol}`}>{p.symbol}</Link> <span className="text-xs text-muted">{p.currency}</span></td>
                <td className="num text-right">{fmtNum(p.quantity, 4)}</td><td className="num text-right">{fmtPrice(p.avg_cost)}</td><td className="num text-right">{fmtPrice(p.last_price)}</td>
                <td className="num text-right">{fmtNum(p.value)}</td><td className={`num text-right ${toneClass(p.unrealized_pnl)}`}>{fmtNum(p.unrealized_pnl)} ({fmtPct(p.unrealized_pct, 1)})</td>
                <td className="num text-right">{p.weight === null ? '—' : fmtPct(p.weight, 1, false)}</td>
                <td>{p.data_status === 'synthetic' ? <Pill tone="warn">sintético</Pill> : <span className="text-xs text-muted">{p.provider}</span>}</td></tr>))}</tbody></table></div>)}
      </Section>

      <div className="grid md:grid-cols-3 gap-4">
        <Section title="Distribución">
          {Object.keys(s.allocation_by_category).length ? Object.entries(s.allocation_by_category).map(([k, v]) => <Kv key={k} k={k} v={fmtPct(v, 1, false)} />) : <p className="text-sm text-muted">—</p>}
          <Kv k="Concentración (HHI)" v={fmtNum(s.concentration_hhi, 2)} hint={s.concentration_note ?? ''} />
          {Object.entries(s.allocation_by_currency).map(([k, v]) => <Kv key={k} k={`Exposición ${k}`} v={fmtNum(v)} />)}
        </Section>
        <Section title="Riesgo (pro forma)">
          {s.risk.available ? (<>
            <Kv k="Volatilidad anualizada" v={fmtPct(s.risk.annualized_volatility, 1, false)} /><Kv k="Drawdown máximo" v={fmtPct(s.risk.max_drawdown, 1, false)} /><Kv k="VaR 95 % (1 barra)" v={fmtPct(s.risk.var_95_1d, 2, false)} />
            <p className="text-[11px] text-muted mt-2">{s.risk.basis}</p></>) : <p className="text-sm text-muted">{s.risk.reason}</p>}
        </Section>
        <Section title={paper ? 'Orden simulada' : 'Registrar transacción'}>
          {paper ? (
            <form onSubmit={submitOrder} className="space-y-2">
              <Field label="Símbolo"><input className="input" required value={order.symbol} onChange={(e) => setOrder({ ...order, symbol: e.target.value })} placeholder="AAPL" /></Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Lado"><select className="input" value={order.side} onChange={(e) => setOrder({ ...order, side: e.target.value })}><option value="buy">Comprar</option><option value="sell">Vender</option></select></Field>
                <Field label="Cantidad"><input className="input" required inputMode="decimal" value={order.quantity} onChange={(e) => setOrder({ ...order, quantity: e.target.value })} /></Field>
              </div>
              <button className="btn btn-primary w-full" type="submit">Ejecutar (simulada)</button>
              <p className="text-[11px] text-muted">Se ejecuta al último cierre disponible con slippage y comisión simulados. No se envía nada a ningún bróker.</p>
            </form>
          ) : null}
          <form onSubmit={submitTx} className={`space-y-2 ${paper ? 'mt-4 pt-3 border-t border-line' : ''}`}>
            {paper && <div className="text-xs text-muted">Ingresar / retirar efectivo simulado</div>}
            <Field label="Tipo"><select className="input" value={tx.type} onChange={(e) => setTx({ ...tx, type: e.target.value })}>
              <option value="deposit">Ingreso de efectivo</option><option value="withdraw">Retirada de efectivo</option>
              {!paper && <><option value="buy">Compra</option><option value="sell">Venta</option></>}</select></Field>
            {tx.type === 'buy' || tx.type === 'sell' ? (<>
              <Field label="Símbolo"><input className="input" required value={tx.symbol} onChange={(e) => setTx({ ...tx, symbol: e.target.value })} /></Field>
              <div className="grid grid-cols-3 gap-2">
                <Field label="Cantidad"><input className="input" required inputMode="decimal" value={tx.quantity} onChange={(e) => setTx({ ...tx, quantity: e.target.value })} /></Field>
                <Field label="Precio"><input className="input" required inputMode="decimal" value={tx.price} onChange={(e) => setTx({ ...tx, price: e.target.value })} /></Field>
                <Field label="Comisión"><input className="input" inputMode="decimal" value={tx.fee} onChange={(e) => setTx({ ...tx, fee: e.target.value })} /></Field>
              </div></>) : <Field label={`Importe (${cur})`}><input className="input" required inputMode="decimal" value={tx.amount} onChange={(e) => setTx({ ...tx, amount: e.target.value })} /></Field>}
            <button className="btn w-full" type="submit">Registrar</button>
          </form>
        </Section>
      </div>

      <Section title="Historial de operaciones">
        {s.transactions.length === 0 ? <p className="text-sm text-muted">Sin operaciones.</p> : (
          <div className="overflow-x-auto"><table className="t"><thead><tr><th>Fecha</th><th>Tipo</th><th>Activo</th><th className="text-right">Cantidad</th><th className="text-right">Precio</th><th className="text-right">Comisión</th><th className="text-right">Importe</th><th>Nota</th></tr></thead>
            <tbody>{[...s.transactions].reverse().map((t) => (<tr key={t.id}><td className="text-muted">{fmtDateTime(t.ts)}</td><td>{t.type}</td><td>{t.symbol ?? '—'}</td>
              <td className="num text-right">{t.quantity ?? '—'}</td><td className="num text-right">{t.price ? fmtPrice(t.price) : '—'}</td><td className="num text-right">{fmtNum(t.fee)}</td><td className="num text-right">{t.amount ? fmtNum(t.amount) : '—'}</td>
              <td className="text-xs text-muted max-w-xs truncate" title={t.note}>{t.note}</td></tr>))}</tbody></table></div>)}
      </Section>
    </div>
  )
}

export default function Portfolios() {
  const list = useAsync(() => api.portfolios(), [])
  const [params, setParams] = useSearchParams()
  const [form, setForm] = useState({ name: '', base_currency: 'USD', paper: false })
  const [err, setErr] = useState<string | null>(null)
  const selected = Number(params.get('id')) || list.data?.portfolios[0]?.id

  const create = (e: FormEvent) => {
    e.preventDefault()
    api.portfolioCreate(form).then((p) => { setErr(null); setForm({ ...form, name: '' }); list.reload(); setParams({ id: String(p.id) }) }).catch((x: Error) => setErr(x.message))
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Carteras y simulador</h1>
      <p className="text-sm text-muted">Carteras manuales y de paper trading. No hace falta cuenta de bróker y nada sale de tu equipo. Sin conversión de divisas: las posiciones en otra moneda se informan aparte.</p>
      <div className="grid lg:grid-cols-4 gap-4">
        <div className="space-y-4">
          <Section title="Mis carteras">
            {list.loading && !list.data ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> : (
              <ul className="space-y-1">{list.data!.portfolios.map((p) => (
                <li key={p.id}><button className={`w-full text-left px-3 py-2 rounded-lg text-sm ${p.id === selected ? 'bg-panel2 border border-accent' : 'hover:bg-panel2 border border-transparent'}`} onClick={() => setParams({ id: String(p.id) })}>
                  {p.name} <span className="text-xs text-muted">{p.base_currency}{p.paper ? ' · simulada' : ''}</span></button></li>))}
                {list.data!.portfolios.length === 0 && <li className="text-sm text-muted">Crea tu primera cartera.</li>}</ul>)}
          </Section>
          <Section title="Nueva cartera">
            <form onSubmit={create} className="space-y-2">
              <Field label="Nombre"><input className="input" required maxLength={80} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Moneda base"><input className="input" required pattern="[A-Za-z]{3}" value={form.base_currency} onChange={(e) => setForm({ ...form, base_currency: e.target.value.toUpperCase() })} /></Field>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.paper} onChange={(e) => setForm({ ...form, paper: e.target.checked })} /> Paper trading (simulada)</label>
              <button className="btn btn-primary w-full" type="submit">Crear</button>
              {err && <p role="alert" className="text-xs text-down">{err}</p>}
            </form>
          </Section>
        </div>
        <div className="lg:col-span-3">{selected ? <Detail key={selected} id={selected} onDeleted={() => { setParams({}); list.reload() }} /> : <p className="text-sm text-muted">Selecciona o crea una cartera.</p>}</div>
      </div>
    </div>
  )
}
