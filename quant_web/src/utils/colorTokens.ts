/**
 * 统一颜色与格式化工具
 *
 * 替代各页面中硬编码的 #ef5350 / #26a69a / #ff9800 等颜色值。
 * 颜色来源：src/assets/themes/naive-theme.ts → CSS 变量
 */
export const CHART_COLORS = {
  up: 'var(--color-stock-up, #FF5252)',
  down: 'var(--color-stock-down, #00E676)',
  flat: 'var(--color-stock-flat, #8898B8)',
  primary: 'var(--color-primary, #448AFF)',
  warning: 'var(--color-warning, #FFB74D)',
  chartBg: 'var(--color-bg-card, #1a1a1a)',
  chartText: 'var(--color-text-secondary, #ccc)',
} as const

/** 涨跌颜色：正→up，负→down，零→flat */
export function pctColor(v: number | null | undefined): string {
  if (v == null) return CHART_COLORS.flat
  if (v > 0) return CHART_COLORS.up
  if (v < 0) return CHART_COLORS.down
  return CHART_COLORS.flat
}

/** 涨跌幅文本：+X.XX% / -X.XX% / -- */
export function pctText(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(decimals)}%`
}

/** 金额格式化：XX.XX亿 / XX.XX万 / raw */
export function formatAmount(v: number | null | undefined): string {
  if (v == null) return '--'
  const abs = Math.abs(v)
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(v / 1e4).toFixed(2)}万`
  return v.toFixed(2)
}

/** 价格格式化 */
export function formatPrice(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  return v.toFixed(decimals)
}

/** 成交量格式化 */
export function formatVolume(v: number | null | undefined): string {
  if (v == null) return '--'
  const abs = Math.abs(v)
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿手`
  if (abs >= 1e4) return `${(v / 1e4).toFixed(2)}万手`
  return `${v}手`
}

/** 市值格式化 */
export function formatMarketCap(v: number | null | undefined): string {
  if (v == null) return '--'
  const abs = Math.abs(v)
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)}万亿`
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿`
  return `${(v / 1e4).toFixed(2)}万`
}
