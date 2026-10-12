export interface Provenance {
  provider: string
  status: 'synthetic' | 'delayed' | 'historical' | 'realtime' | string
  status_label: string
  fetched_at: string
  as_of: string | null
  currency: string
  note: string
  warnings: string[]
}
export interface AssetInfo {
  symbol: string; name: string; category: string; category_label: string
  market: string; currency: string; note: string
}
export interface Quote extends AssetInfo {
  price: number; prev_close: number | null; change: number | null; change_pct: number | null
  as_of: string | null; provenance: Provenance; spark: number[]; live_supported?: boolean
}
export interface QuotesResponse {
  quotes: Quote[]; errors: Record<string, string>; last_update: string | null; any_synthetic: boolean
}
export interface ModuleInfo { id: string; label: string; status: 'available' | 'partial' | 'planned'; route: string | null; note?: string }
export interface SourceInfo {
  name: string; label: string; description: string; license_note: string; covers: string[]; enabled: boolean
  history_note: string; ok_count: number; error_count: number; last_ok: string | null
  last_error: string | null; last_error_at: string | null
}
export interface Probabilities {
  available: boolean; reason?: string; n_samples?: number; effective_samples?: number; horizon_bars?: number
  probabilities?: { bajada: number; neutral: number; subida: number }
  definition?: string; method?: string; caveat?: string
}
export interface Validation {
  available: boolean; reason?: string; n_eval?: number; brier?: number; brier_baseline?: number
  log_loss?: number; log_loss_baseline?: number; skill_vs_baseline?: number; verdict?: string; note?: string
}
export interface Signal {
  available: boolean; reason?: string
  direction?: 'BAJISTA' | 'NEUTRAL' | 'ALCISTA'; score?: number; intensity?: number
  thresholds?: Record<string, string>; horizon_text?: string
  uncertainty?: number; uncertainty_label?: string
  components?: Record<string, number>; favorable?: string[]; unfavorable?: string[]; risks?: string[]
  data_used?: string; computed_at?: string; explanation?: string; disclaimer?: string
  probabilities?: Probabilities; validation?: Validation
}
export interface Risk {
  available: boolean; reason?: string; basis?: string; observations?: number
  annualized_volatility?: number; annualized_return?: number; max_drawdown?: number; current_drawdown?: number
  var_95_1d?: number; cvar_95_1d?: number | null; worst_day?: number; best_day?: number; note?: string
}
export interface AssetDetail {
  asset: AssetInfo; provenance: Provenance; quote: Quote; bars: number; first_date: string; last_date: string
  indicators: Record<string, number | null>; returns: Record<string, number | null>
  levels: { support: number[]; resistance: number[] }; risk: Risk; signal: Signal; notes: string[]
}
export interface LinePoint { time: string; value: number }
export interface ChartData {
  symbol: string; provenance: Provenance
  candles: { time: string; open: number; high: number; low: number; close: number }[]
  volume: { time: string; value: number; up: boolean }[]
  overlays: Record<string, LinePoint[]>
  rsi: LinePoint[]; macd: LinePoint[]; macd_signal: LinePoint[]; macd_hist: LinePoint[]
}
export interface Correlations { available: boolean; reason?: string; symbols?: string[]; matrix?: number[][]; overlap?: number; note?: string; any_synthetic?: boolean }
export interface Portfolio { id: number; name: string; base_currency: string; paper: boolean; created_at: string }
export interface PositionRow {
  symbol: string; name: string; category: string | null; currency: string | null; quantity: number; avg_cost: number
  last_price: number | null; value: number | null; cost_basis: number; unrealized_pnl: number | null
  unrealized_pct: number | null; weight: number | null; in_base_currency: boolean; data_status: string | null; provider: string | null
}
export interface Transaction { id: number; ts: string; type: string; symbol: string | null; quantity: number | null; price: number | null; fee: number; amount: number | null; note: string }
export interface PortfolioSummary {
  portfolio: Portfolio; cash: number; invested_value: number; total_value: number; realized_pnl: number
  unrealized_pnl: number; fees_paid: number; positions: PositionRow[]
  allocation_by_category: Record<string, number>; allocation_by_currency: Record<string, number>
  concentration_hhi: number | null; concentration_note: string | null; warnings: string[]
  risk: Risk & { weights_excl_cash?: Record<string, number> }; transactions: Transaction[]
}
export interface BacktestMetrics {
  total_return: number | null; cagr?: number; volatility?: number | null; max_drawdown?: number; sharpe_rf0?: number | null
  trades?: number; win_rate?: number | null; exposure?: number; fees_paid?: number
}
export interface BacktestResult {
  symbol: string; strategy: string; label: string; params: Record<string, number>
  period: { start: string; end: string; bars: number }
  costs: { commission_bps: number; slippage_bps: number; execution: string }
  initial_capital: number; final_equity: number; metrics: BacktestMetrics
  benchmark: BacktestMetrics & { label: string }
  trades: { entry_date: string; entry_price: number; exit_date: string; exit_price: number; qty: number; fees: number; pnl: number; return: number; closed: boolean; note: string | null }[]
  curve: { dates: string[]; equity: number[]; benchmark: number[]; drawdown: number[] }
  warnings: string[]; provenance: Provenance
  segments?: { in_sample: BacktestMetrics; out_of_sample: BacktestMetrics; split_date: string; note: string }
}
export interface StrategyInfo { id: string; label: string; params: Record<string, number> }

const TOKEN_KEY = 'openmarket.token'
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) ?? '' } catch { return '' } }
export const setToken = (t: string) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* sin almacenamiento */ } }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let res: Response
  try {
    res = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor de OpenMarket. ¿Está en marcha?')
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* cuerpo no JSON */ }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => request<{ status: string; version: string; offline: boolean; demo_fallback: boolean; auth_required: boolean }>('/api/health'),
  modules: () => request<{ modules: ModuleInfo[] }>('/api/modules'),
  search: (q: string) => request<{ results: AssetInfo[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  assets: () => request<{ assets: AssetInfo[] }>('/api/assets'),
  quotes: (opts: { symbols?: string[]; category?: string } = {}) => {
    const p = new URLSearchParams()
    if (opts.symbols) p.set('symbols', opts.symbols.join(','))
    if (opts.category) p.set('category', opts.category)
    return request<QuotesResponse>(`/api/quotes?${p}`)
  },
  asset: (s: string, refresh = false) => request<AssetDetail>(`/api/assets/${encodeURIComponent(s)}?refresh=${refresh}`),
  chart: (s: string, bars = 520) => request<ChartData>(`/api/assets/${encodeURIComponent(s)}/chart?bars=${bars}`),
  correlations: (symbols: string[]) => request<Correlations>(`/api/correlations?symbols=${symbols.join(',')}`),
  sources: () => request<{ sources: SourceInfo[]; offline: boolean; demo_fallback: boolean }>('/api/sources'),
  watchlist: () => request<{ symbols: string[] }>('/api/watchlist'),
  watchAdd: (s: string) => request<{ symbols: string[] }>(`/api/watchlist/${encodeURIComponent(s)}`, { method: 'POST' }),
  watchRemove: (s: string) => request<{ symbols: string[] }>(`/api/watchlist/${encodeURIComponent(s)}`, { method: 'DELETE' }),
  strategies: () => request<{ strategies: StrategyInfo[] }>('/api/strategies'),
  backtest: (body: Record<string, unknown>) => request<BacktestResult>('/api/backtest', json('POST', body)),
  portfolios: () => request<{ portfolios: Portfolio[] }>('/api/portfolios'),
  portfolioCreate: (body: { name: string; base_currency: string; paper: boolean }) => request<Portfolio>('/api/portfolios', json('POST', body)),
  portfolioDelete: (id: number) => request<{ deleted: number }>(`/api/portfolios/${id}`, { method: 'DELETE' }),
  portfolio: (id: number) => request<PortfolioSummary>(`/api/portfolios/${id}`),
  portfolioTx: (id: number, body: Record<string, unknown>) => request<Transaction>(`/api/portfolios/${id}/transactions`, json('POST', body)),
  paperOrder: (id: number, body: Record<string, unknown>) => request<Transaction>(`/api/portfolios/${id}/paper-order`, json('POST', body)),
  live: (symbols: string[]) => request<LiveResponse>(`/api/live?symbols=${symbols.map(encodeURIComponent).join(',')}`),
  screener: (category?: string, direction?: string) => {
    const p = new URLSearchParams()
    if (category) p.set('category', category)
    if (direction) p.set('direction', direction)
    return request<ScreenerResponse>(`/api/screener?${p}`)
  },
  alerts: () => request<{ alerts: AlertItem[]; kinds: Record<string, string> }>('/api/alerts'),
  alertCreate: (body: { symbol: string; kind: string; threshold: number; note: string }) => request<AlertItem>('/api/alerts', json('POST', body)),
  alertDelete: (id: number) => request<{ deleted: number }>(`/api/alerts/${id}`, { method: 'DELETE' }),
  alertRearm: (id: number) => request<{ rearmed: number }>(`/api/alerts/${id}/rearm`, { method: 'POST' }),
  alertsCheck: () => request<AlertCheck>('/api/alerts/check', { method: 'POST' }),
  toolOption: (body: Record<string, unknown>) => request<Record<string, any>>('/api/tools/option', json('POST', body)), // eslint-disable-line @typescript-eslint/no-explicit-any
  toolBond: (body: Record<string, unknown>) => request<Record<string, any>>('/api/tools/bond', json('POST', body)), // eslint-disable-line @typescript-eslint/no-explicit-any
  diagnostics: () => request<{ results: DiagResult[]; offline: boolean }>('/api/diagnostics', { method: 'POST' }),
}

export interface LiveQuoteData {
  symbol: string; price: number; as_of: string; provider: string; status: string; status_label: string; currency: string
  open_today: number | null; high_today: number | null; low_today: number | null; bid: number | null; ask: number | null
  volume_24h: number | null; change_pct_today: number | null; note: string
}
export interface LiveResponse { quotes: Record<string, LiveQuoteData>; errors: Record<string, string>; server_time: string }
export interface ScreenerRow extends AssetInfo {
  price: number; change_pct: number | null; direction: string; score: number; uncertainty_label: string
  rsi14: number | null; ret_1m: number | null; ret_3m: number | null; vol_annualized: number | null
  max_drawdown: number | null; dist_sma200: number | null; data_status: string; data_status_label: string; provider: string
}
export interface ScreenerResponse { rows: ScreenerRow[]; missing: string[]; any_synthetic: boolean; method: string }
export interface AlertItem {
  id: number; symbol: string; kind: string; kind_label: string; threshold: number; note: string; active: boolean
  created_at: string; triggered_at: string | null; last_value: number | null; last_source: string | null
}
export interface AlertCheck { triggered: (AlertItem & { message: string })[]; skipped: { id: number; symbol: string; reason: string }[]; evaluated: number }
export interface DiagResult { provider: string; kind: string; symbol: string; ok: boolean; detail: string }
