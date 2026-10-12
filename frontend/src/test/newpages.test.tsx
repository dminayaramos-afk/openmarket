// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from '../App'
import modules from './fixtures/modules.json'
import sources from './fixtures/sources.json'
import health from './fixtures/health.json'
import live from './fixtures/live_btc.json'
import screener from './fixtures/screener_etf.json'
import alerts from './fixtures/alerts.json'
import alertsCheck from './fixtures/alerts_check.json'
import option from './fixtures/option.json'
import bond from './fixtures/bond.json'
import diag from './fixtures/diag.json'

vi.mock('../components/PriceChart', () => ({ PriceChart: () => null }))
vi.mock('../components/EquityChart', () => ({ EquityChart: () => null }))

const calls: string[] = []
beforeEach(() => {
  calls.length = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url); calls.push(`${init?.method ?? 'GET'} ${u}`)
    const table: [string, unknown][] = [
      ['/api/modules', modules], ['/api/sources', sources], ['/api/health', health], ['/api/screener', screener],
      ['/api/alerts/check', alertsCheck], ['/api/alerts', alerts], ['/api/tools/option', option], ['/api/tools/bond', bond],
      ['/api/diagnostics', diag], ['/api/live', live],
    ]
    const hit = table.find(([p]) => u.startsWith(p))
    if (!hit) return new Response(JSON.stringify({ detail: `sin fixture: ${u}` }), { status: 404 })
    return new Response(JSON.stringify(hit[1]), { status: 200 })
  }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const go = (path: string) => { window.history.pushState({}, '', path); return render(<App />) }

describe('pantallas de la versión 0.2', () => {
  it('Buscador de oportunidades lista activos ordenados y avisa de datos sintéticos', async () => {
    go('/oportunidades')
    await waitFor(() => expect(screen.getByText(/Resultados \(/)).toBeTruthy())
    expect(screen.getAllByText(/Datos sintéticos/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/no estima rentabilidad futura/)).toBeTruthy()
  })
  it('Alertas muestra la alerta disparada y evalúa al abrir', async () => {
    go('/alertas')
    await waitFor(() => expect(screen.getByText('Mis alertas')).toBeTruthy())
    await waitFor(() => expect(screen.getAllByText(/disparada/i).length).toBeGreaterThan(0))
    expect(calls.some((c) => c.startsWith('POST /api/alerts/check'))).toBe(true)
  })
  it('Calculadora de opciones devuelve el precio teórico', async () => {
    go('/derivados')
    fireEvent.click(screen.getByText('Calcular'))
    await waitFor(() => expect(screen.getByTestId('option-result')).toBeTruthy())
    expect(screen.getByTestId('option-result').textContent).toContain('10,45')
  })
  it('Calculadora de bonos devuelve el resultado', async () => {
    go('/bonos')
    fireEvent.click(screen.getByText('Calcular'))
    await waitFor(() => expect(screen.getByTestId('bond-result')).toBeTruthy())
  })
  it('Configuración ejecuta el diagnóstico de proveedores', async () => {
    go('/configuracion')
    await waitFor(() => expect(screen.getByText('Comprobar proveedores de datos')).toBeTruthy())
    fireEvent.click(screen.getByText('Comprobar ahora'))
    await waitFor(() => expect(screen.getByTestId('diag-results')).toBeTruthy())
    expect(screen.getAllByText(/FALLO|OK/).length).toBeGreaterThan(0)
  })
})
