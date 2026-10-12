import { useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api, type ModuleInfo } from './api'
import { useAsync, useTheme } from './hooks'
import { SearchBox, Pill } from './components/ui'
import Dashboard from './pages/Dashboard'
import { CategoryPage, GlobalMarkets } from './pages/Markets'
import Asset from './pages/Asset'
import Portfolios from './pages/Portfolios'
import Backtest from './pages/Backtest'
import Settings from './pages/Settings'
import Screener from './pages/Screener'
import Alerts from './pages/Alerts'
import { Bonds, Options } from './pages/Tools'
import ComingSoon from './pages/ComingSoon'

function NavItem({ m, onNavigate }: { m: ModuleInfo; onNavigate: () => void }) {
  if (m.status === 'planned' || !m.route) {
    return (
      <NavLink to={`/pronto/${m.id}`} onClick={onNavigate} className={({ isActive }) => `flex items-center justify-between px-3 py-1.5 rounded-lg text-sm opacity-60 hover:opacity-100 ${isActive ? 'bg-panel2' : ''}`}>
        <span>{m.label}</span><span className="text-[10px] text-muted">pronto</span>
      </NavLink>
    )
  }
  return (
    <NavLink to={m.route} end={m.route === '/'} onClick={onNavigate} title={m.note}
      className={({ isActive }) => `flex items-center justify-between px-3 py-1.5 rounded-lg text-sm ${isActive ? 'bg-panel2 text-ink border border-line' : 'text-muted hover:text-ink hover:bg-panel2 border border-transparent'}`}>
      <span>{m.label}</span>{m.status === 'partial' && <Pill tone="warn" title={m.note}>parcial</Pill>}
    </NavLink>
  )
}

function Shell() {
  const mods = useAsync(() => api.modules(), [])
  const [theme, toggle] = useTheme()
  const [open, setOpen] = useState(false)
  // Evita duplicados de ruta en el menú (varias secciones apuntan a la misma pantalla)
  const seen = new Set<string>()
  const modules = (mods.data?.modules ?? []).filter((m) => { const k = m.route ? `${m.route}|${m.label}` : m.id; if (seen.has(k)) return false; seen.add(k); return true })

  return (
    <div className="min-h-full flex">
      <aside className={`${open ? 'flex' : 'hidden'} lg:flex fixed lg:sticky top-0 z-40 h-screen w-64 shrink-0 flex-col bg-panel border-r border-line p-3 overflow-y-auto`} aria-label="Navegación principal">
        <Link to="/" className="flex items-center gap-2.5 px-2 py-3" onClick={() => setOpen(false)}>
          <img src="/logo.png" alt="" width={36} height={36} className="rounded-lg" />
          <span className="text-lg font-semibold tracking-tight">OpenMarket</span>
        </Link>
        <nav className="mt-2 space-y-0.5 flex-1">
          {mods.loading && <div className="text-xs text-muted px-3">Cargando…</div>}
          {mods.error && <div className="text-xs text-down px-3">{mods.error}</div>}
          {modules.map((m) => <NavItem key={m.id} m={m} onNavigate={() => setOpen(false)} />)}
        </nav>
        <p className="text-[10px] text-muted px-2 pt-3">Análisis informativo. No es asesoramiento financiero. Código abierto (AGPL-3.0).</p>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-20 bg-bg/90 backdrop-blur border-b border-line px-4 py-2.5 flex items-center gap-3">
          <button className="btn lg:hidden" aria-label="Abrir menú" aria-expanded={open} onClick={() => setOpen((o) => !o)}>☰</button>
          <SearchBox />
          <div className="ml-auto"><button className="btn" onClick={toggle} aria-label="Cambiar tema">{theme === 'dark' ? '☾' : '☀'}</button></div>
        </header>
        <main className="p-4 md:p-6 max-w-[1400px] mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mercados" element={<GlobalMarkets />} />
            <Route path="/mercado/:category" element={<CategoryPage />} />
            <Route path="/activo/:symbol" element={<Asset />} />
            <Route path="/carteras" element={<Portfolios />} />
            <Route path="/backtesting" element={<Backtest />} />
            <Route path="/oportunidades" element={<Screener />} />
            <Route path="/alertas" element={<Alerts />} />
            <Route path="/bonos" element={<Bonds />} />
            <Route path="/derivados" element={<Options />} />
            <Route path="/configuracion" element={<Settings />} />
            <Route path="/pronto/:id" element={<ComingSoon />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return <BrowserRouter><Shell /></BrowserRouter>
}
