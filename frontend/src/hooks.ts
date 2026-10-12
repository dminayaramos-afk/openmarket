import { useCallback, useEffect, useRef, useState } from 'react'

export interface Async<T> { data: T | null; error: string | null; loading: boolean; reload: () => void }

/** Carga asíncrona con estados explícitos de carga y error (nunca deja la pantalla en blanco). */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fnRef.current()
      .then((d) => { if (alive) { setData(d); setLoading(false) } })
      .catch((e: unknown) => { if (alive) { setError(e instanceof Error ? e.message : String(e)); setLoading(false) } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

export function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState<string>(() => {
    try { return localStorage.getItem('openmarket.theme') ?? 'dark' } catch { return 'dark' }
  })
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem('openmarket.theme', theme) } catch { /* sin almacenamiento */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

/** Repite una carga cada `ms` milisegundos mientras la pestaña está visible. Conserva el último dato si una carga falla. */
export function usePolling<T>(fn: () => Promise<T>, ms: number, deps: unknown[]): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let alive = true
    const run = () => {
      if (typeof document !== 'undefined' && document.hidden) return
      fnRef.current()
        .then((d) => { if (alive) { setData(d); setError(null) } })
        .catch((e: unknown) => { if (alive) setError(e instanceof Error ? e.message : String(e)) })
    }
    run()
    const id = setInterval(run, ms)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, ms])
  return { data, error }
}
