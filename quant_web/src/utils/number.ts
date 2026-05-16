export function formatNumber(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return Number(value).toFixed(decimals);
}

export function formatCurrency(
  value: number | null | undefined,
  symbol = "¥",
  decimals = 2,
): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return `${symbol}${Number(value).toFixed(decimals)}`;
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 2,
): string {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return `${Number(value * 100).toFixed(decimals)}%`;
}
