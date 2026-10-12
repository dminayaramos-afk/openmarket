import { useState } from 'react'
import { api } from '../api'
import { fmtNum, fmtPct } from '../format'
import { Kv, Section } from '../components/ui'

type Res = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
const num = (s: string) => Number(s.replace(',', '.'))

function Field({ label, value, onChange, hint }: { label: string; value: string; onChange: (v: string) => void; hint?: string }) {
  return <label className="grid gap-1 text-sm">{label}<input className="input" aria-label={label} inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} />{hint && <span className="text-[11px] text-muted">{hint}</span>}</label>
}

export function Options() {
  const [f, setF] = useState({ spot: '100', strike: '100', days: '365', rate: '5', vol: '20', price: '' })
  const [kind, setKind] = useState('call')
  const [res, setRes] = useState<Res | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }))
  const run = () => {
    setErr(null)
    const body: Record<string, unknown> = { kind, spot: num(f.spot), strike: num(f.strike), days: num(f.days), rate: num(f.rate) / 100 }
    if (f.price.trim()) body.market_price = num(f.price); else body.volatility = num(f.vol) / 100
    api.toolOption(body).then(setRes).catch((e: Error) => { setRes(null); setErr(e.message) })
  }
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Derivados: calculadora de opciones</h1>
      <p className="text-sm text-muted">Modelo Black-Scholes-Merton para opciones europeas. Es una calculadora teórica: no usa precios de mercado ni cadenas de opciones reales.</p>
      <Section title="Datos">
        <div className="grid sm:grid-cols-3 gap-3">
          <label className="grid gap-1 text-sm">Tipo<select className="input" aria-label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}><option value="call">Call</option><option value="put">Put</option></select></label>
          <Field label="Precio del subyacente" value={f.spot} onChange={set('spot')} />
          <Field label="Strike" value={f.strike} onChange={set('strike')} />
          <Field label="Días hasta vencimiento" value={f.days} onChange={set('days')} />
          <Field label="Tipo libre de riesgo (% anual)" value={f.rate} onChange={set('rate')} />
          <Field label="Volatilidad (% anual)" value={f.vol} onChange={set('vol')} hint="Se ignora si indicas el precio de mercado." />
          <Field label="Precio de mercado de la opción (opcional)" value={f.price} onChange={set('price')} hint="Si lo rellenas, se calcula la volatilidad implícita." />
        </div>
        <button className="btn btn-primary mt-3" onClick={run}>Calcular</button>
        {err && <p role="alert" className="text-sm text-down mt-2">{err}</p>}
      </Section>
      {res && (
        <Section title="Resultado">
          <div className="grid sm:grid-cols-2 gap-x-8 text-sm" data-testid="option-result">
            <Kv k="Precio teórico" v={fmtNum(res.theoretical_price, 4)} /><Kv k="Valor intrínseco" v={fmtNum(res.intrinsic_value, 4)} />
            <Kv k="Valor temporal" v={fmtNum(res.time_value, 4)} />
            <Kv k={res.volatility_is_implied ? 'Volatilidad implícita' : 'Volatilidad usada'} v={fmtPct(res.volatility_used, 2, false)} />
            {Object.entries(res.greeks as Record<string, number>).map(([k, v]) => <Kv key={k} k={k} v={fmtNum(v, 4)} />)}
          </div>
          <p className="text-[11px] text-muted mt-3">{res.model} {res.units}</p>
        </Section>)}
    </div>
  )
}

export function Bonds() {
  const [f, setF] = useState({ face: '100', coupon: '5', years: '10', ytm: '5', price: '' })
  const [freq, setFreq] = useState('1')
  const [res, setRes] = useState<Res | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }))
  const run = () => {
    setErr(null)
    const body: Record<string, unknown> = { face: num(f.face), coupon: num(f.coupon) / 100, years: num(f.years), frequency: Number(freq) }
    if (f.price.trim()) body.price = num(f.price); else body.ytm = num(f.ytm) / 100
    api.toolBond(body).then(setRes).catch((e: Error) => { setRes(null); setErr(e.message) })
  }
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Bonos: calculadora</h1>
      <p className="text-sm text-muted">Precio, rendimiento, duración y convexidad de un bono con cupón fijo. Es teórica: no hay datos de mercado de bonos ni curvas de tipos.</p>
      <Section title="Datos">
        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Nominal" value={f.face} onChange={set('face')} />
          <Field label="Cupón (% anual)" value={f.coupon} onChange={set('coupon')} />
          <Field label="Años hasta vencimiento" value={f.years} onChange={set('years')} />
          <label className="grid gap-1 text-sm">Pagos al año<select className="input" aria-label="Pagos al año" value={freq} onChange={(e) => setFreq(e.target.value)}>{['1', '2', '4', '12'].map((x) => <option key={x}>{x}</option>)}</select></label>
          <Field label="Rendimiento YTM (% anual)" value={f.ytm} onChange={set('ytm')} hint="Se ignora si indicas el precio." />
          <Field label="Precio (opcional)" value={f.price} onChange={set('price')} hint="Si lo rellenas, se calcula el rendimiento." />
        </div>
        <button className="btn btn-primary mt-3" onClick={run}>Calcular</button>
        {err && <p role="alert" className="text-sm text-down mt-2">{err}</p>}
      </Section>
      {res && (
        <Section title="Resultado">
          <div className="grid sm:grid-cols-2 gap-x-8 text-sm" data-testid="bond-result">
            <Kv k={res.ytm_is_computed ? 'Rendimiento calculado (YTM)' : 'Rendimiento (YTM)'} v={fmtPct(res.ytm, 3, false)} />
            {Object.entries(res).filter(([k, v]) => typeof v === 'number' && k !== 'ytm').map(([k, v]) => <Kv key={k} k={k} v={fmtNum(v as number, 4)} />)}
          </div>
          <p className="text-[11px] text-muted mt-3">{res.model}</p>
        </Section>)}
    </div>
  )
}
