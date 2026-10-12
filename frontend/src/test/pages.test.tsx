// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import App from '../App'
import modules from './fixtures/modules.json'
import quotes from './fixtures/quotes.json'
import sources from './fixtures/sources.json'
import watchlist from './fixtures/watchlist.json'
import portfolios from './fixtures/portfolios.json'
import strategies from './fixtures/strategies.json'
import health from './fixtures/health.json'
import aapl from './fixtures/assets_AAPL.json'
import corr from './fixtures/correlations.json'

// jsdom no implementa canvas: los gráficos se comprueban en el navegador, no aquí
vi.mock('../components/PriceChart', () => ({ PriceChart: () => null }))
vi.mock('../components/EquityChart', () => ({ EquityChart: () => null }))

// Respuestas reales de la API capturadas con el servidor en marcha
const routes: Record<string, unknown> = {
  '/api/modules': modules, '/api/sources': sources, '/api/watchlist': watchlist, '/api/portfolios': portfolios,
  '/api/strategies': strategies, '/api/health': health, '/api/assets/AAPL?refresh=false': aapl,
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url)
    const data = u.startsWith('/api/quotes') ? quotes : u.startsWith('/api/correlations') ? corr : routes[u]
    if (data === undefined) return new Response(JSON.stringify({ detail: `sin fixture: ${u}` }), { status: 404 })
    return new Response(JSON.stringify(data), { status: 200 })
  }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const go = (path: string) => { window.history.pushState({}, '', path); return render(<App />) }

describe('páginas (datos reales capturados de la API)', () => {
  it('Dashboard muestra aviso de datos sintéticos, índices y fuentes', async () => {
    go('/')
    await waitFor(() => expect(screen.getByText('Índices principales')).toBeTruthy())
    expect(screen.getAllByText(/Datos sintéticos/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Estado de las fuentes de datos')).toBeTruthy()
    expect(screen.getAllByText('S&P 500').length).toBeGreaterThan(0)
  })
  it('la navegación refleja el estado real de implementación', async () => {
    go('/')
    await waitFor(() => expect(screen.getAllByText('Bonos').length).toBeGreaterThan(0))
    expect(screen.getAllByText('pronto').length).toBeGreaterThan(3)
    expect(screen.getAllByText('parcial').length).toBeGreaterThan(0)
  })
  it('Ficha de activo muestra señal, probabilidades, validación y procedencia', async () => {
    go('/activo/AAPL')
    await waitFor(() => expect(screen.getByText('Señal alcista / neutral / bajista')).toBeTruthy())
    expect(screen.getByText(/Probabilidades empíricas/)).toBeTruthy()
    expect(screen.getByText(/Validación fuera de muestra/)).toBeTruthy()
    expect(screen.getAllByText('sintético').length).toBeGreaterThan(0)
  })
  it('Mercados por categoría, Carteras, Backtesting, Configuración y Próximamente renderizan', async () => {
    for (const [path, text] of [['/mercado/stock', /instrumentos/], ['/carteras', 'Carteras y simulador'], ['/backtesting', 'Configuración'], ['/configuracion', 'Fuentes de datos'], ['/pronto/bonds', /en desarrollo/]] as [string, string | RegExp][]) {
      go(path)
      await waitFor(() => expect(screen.getAllByText(text).length).toBeGreaterThan(0))
      cleanup()
    }
  })
  it('un error de la API se muestra con opción de reintento (no pantalla en blanco)', async () => {
    ;(fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async () => new Response(JSON.stringify({ detail: 'boom' }), { status: 503 }))
    go('/mercado/crypto')
    await waitFor(() => expect(screen.getByText('No se pudo cargar')).toBeTruthy())
    expect(screen.getByText('Reintentar')).toBeTruthy()
  })
})
