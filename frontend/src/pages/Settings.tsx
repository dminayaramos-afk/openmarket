import { useState } from 'react'
import { api, getToken, setToken } from '../api'
import { useAsync, useTheme } from '../hooks'
import { fmtDateTime } from '../format'
import { ErrorBox, Loading, Pill, Section } from '../components/ui'

export default function Settings() {
  const health = useAsync(() => api.health(), [])
  const sources = useAsync(() => api.sources(), [])
  const [theme, toggleTheme] = useTheme()
  const [token, setTok] = useState(getToken())
  const [saved, setSaved] = useState(false)

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Configuración</h1>
      <div className="grid md:grid-cols-2 gap-4">
        <Section title="Apariencia"><button className="btn" onClick={toggleTheme}>Tema: {theme === 'dark' ? 'oscuro' : 'claro'} (cambiar)</button></Section>
        <Section title="Acceso a la API">
          <p className="text-sm text-muted mb-2">Si el servidor define <code>OPENMARKET_API_TOKEN</code>, introdúcelo aquí. Se guarda solo en este navegador.</p>
          <div className="flex gap-2"><input type="password" className="input" aria-label="Token de acceso" value={token} onChange={(e) => { setTok(e.target.value); setSaved(false) }} placeholder="Token (opcional)" />
            <button className="btn" onClick={() => { setToken(token); setSaved(true) }}>Guardar</button></div>
          {saved && <p className="text-xs text-up mt-1" role="status">Guardado. Recarga la página.</p>}
        </Section>
      </div>
      <Section title="Servidor">
        {health.loading ? <Loading /> : health.error ? <ErrorBox message={health.error} onRetry={health.reload} /> : (
          <ul className="text-sm space-y-1"><li>Versión: <strong>{health.data!.version}</strong></li>
            <li>Modo sin conexión: {health.data!.offline ? <Pill tone="warn">activado</Pill> : 'no'}</li>
            <li>Respaldo con datos sintéticos: {health.data!.demo_fallback ? <Pill tone="warn">activado</Pill> : 'desactivado'}</li>
            <li>Token de acceso requerido: {health.data!.auth_required ? 'sí' : 'no (solo seguro en localhost)'}</li></ul>)}
      </Section>
      <Section title="Fuentes de datos">
        {sources.loading ? <Loading /> : sources.error ? <ErrorBox message={sources.error} onRetry={sources.reload} /> : (
          <div className="space-y-3">{sources.data!.sources.map((s) => (
            <div key={s.name} className="border-b border-line pb-3 last:border-0">
              <div className="flex items-center gap-2"><strong>{s.label}</strong>{!s.enabled && <Pill tone="flat">desactivada</Pill>}<span className="text-xs text-muted">cubre: {s.covers.join(', ')}</span></div>
              <p className="text-sm text-muted">{s.description}</p>
              <p className="text-xs text-muted">{s.license_note} {s.history_note}</p>
              <p className="text-xs mt-1">Aciertos: {s.ok_count} · Errores: {s.error_count}{s.last_error ? <span className="text-down"> · último error ({fmtDateTime(s.last_error_at)}): {s.last_error}</span> : ''}</p>
            </div>))}</div>)}
      </Section>
      <Section title="Cómo leer el estado de un dato">
        <ul className="text-sm text-muted list-disc ml-5 space-y-1">
          <li><strong className="text-ink">sintético</strong>: generado artificialmente para probar la interfaz; nunca es un precio real.</li>
          <li><strong className="text-ink">retrasado</strong>: dato real de un proveedor gratuito, normalmente cierre diario; no es tiempo real.</li>
          <li><strong className="text-ink">histórico</strong>: serie pasada sin pretensión de actualidad.</li>
        </ul>
      </Section>
    </div>
  )
}
