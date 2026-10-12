// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { LivePrice } from '../components/LivePrice'
import live from './fixtures/live_btc.json'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('LivePrice', () => {
  it('muestra precio con etiqueta «tiempo real» y su proveedor', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(live), { status: 200 })))
    render(<LivePrice symbol="BTC-USD" enabled />)
    await waitFor(() => expect(screen.getByTestId('live-box')).toBeTruthy())
    expect(screen.getByText('tiempo real')).toBeTruthy()
    expect(screen.getByTestId('live-box').textContent).toContain('Kraken')
  })
  it('sin proveedor explica cómo activarlo y no muestra ningún precio', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 500 })))
    render(<LivePrice symbol="AAPL" enabled={false} />)
    expect(screen.getByTestId('live-off').textContent).toContain('OPENMARKET_FINNHUB_KEY')
    expect(screen.queryByTestId('live-box')).toBeNull()
  })
  it('si el proveedor falla lo dice, sin inventar precio', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ quotes: {}, errors: { 'BTC-USD': 'timeout' }, server_time: 'x' }), { status: 200 })))
    render(<LivePrice symbol="BTC-USD" enabled />)
    await waitFor(() => expect(screen.getByTestId('live-wait').textContent).toContain('timeout'))
  })
})
