// 数字格式化
export function formatNumber(value, decimals = 2) {
  if (isNaN(value)) return '-';
  return Number(value).toFixed(decimals);
}
export function formatCurrency(value, symbol = '¥', decimals = 2) {
  if (isNaN(value)) return '-';
  return `${symbol}${Number(value).toFixed(decimals)}`;
}
export function formatPercent(value, decimals = 2) {
  if (isNaN(value)) return '-';
  return `${Number(value * 100).toFixed(decimals)}%`;
}