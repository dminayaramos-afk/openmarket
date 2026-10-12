const nf = (min: number, max: number) => new Intl.NumberFormat('es-ES', { minimumFractionDigits: min, maximumFractionDigits: max })

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return nf(digits, digits).format(v)
}

/** Precio con decimales adaptados a su magnitud (forex 1,0845; acciones 182,31; cripto 64.210,50). */
export function fmtPrice(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  const d = a >= 1000 ? 2 : a >= 10 ? 2 : a >= 1 ? 4 : 6
  return nf(d, d).format(v)
}

export function fmtPct(v: number | null | undefined, digits = 2, sign = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const s = nf(digits, digits).format(v * 100)
  return `${sign && v > 0 ? '+' : ''}${s} %`
}

export function toneClass(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return 'text-flat'
  return v > 0 ? 'text-up' : 'text-down'
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' })
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-ES', { dateStyle: 'medium', timeZone: 'UTC' })
}

/** Color de mapa de calor: verde/rojo con intensidad proporcional al cambio (saturada en ±3 %). */
export function heatColor(change: number | null | undefined): string {
  if (change === null || change === undefined || Number.isNaN(change)) return 'var(--panel-2)'
  const k = Math.min(Math.abs(change) / 0.03, 1)
  const base = change >= 0 ? 'var(--up)' : 'var(--down)'
  return `color-mix(in srgb, ${base} ${Math.round(18 + k * 62)}%, var(--panel-2))`
}
