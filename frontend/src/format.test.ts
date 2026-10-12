import { describe, expect, it } from 'vitest'
import { fmtPct, fmtPrice, fmtNum, heatColor, toneClass } from './format'

describe('format', () => {
  it('formats null/NaN as dash', () => {
    expect(fmtNum(null)).toBe('—')
    expect(fmtPct(undefined)).toBe('—')
    expect(fmtPrice(Number.NaN)).toBe('—')
  })
  it('formats percentages with sign and Spanish decimals', () => {
    expect(fmtPct(0.0123)).toBe('+1,23 %')
    expect(fmtPct(-0.05)).toBe('-5,00 %')
    expect(fmtPct(0.5, 1, false)).toBe('50,0 %')
  })
  it('adapts price decimals', () => {
    expect(fmtPrice(1.0845)).toBe('1,0845')
    expect(fmtPrice(182.314)).toBe('182,31')
  })
  it('tone classes', () => {
    expect(toneClass(1)).toBe('text-up')
    expect(toneClass(-1)).toBe('text-down')
    expect(toneClass(0)).toBe('text-flat')
    expect(toneClass(null)).toBe('text-flat')
  })
  it('heat color falls back for missing data', () => {
    expect(heatColor(null)).toBe('var(--panel-2)')
    expect(heatColor(0.05)).toContain('var(--up)')
    expect(heatColor(-0.05)).toContain('var(--down)')
  })
})
