const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
})

export function formatDate(value: string | null): string {
  return value ? dateFormatter.format(new Date(value)) : "尚无记录"
}

export function formatNumber(value: number | null): string {
  return value === null ? "—" : new Intl.NumberFormat("zh-CN").format(value)
}

export function formatLatency(value: number | null): string {
  if (value === null) return "—"
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`
  return `${Math.round(value)} ms`
}

export function successRate(success: number, total: number): string {
  return total === 0 ? "—" : `${Math.round((success / total) * 100)}%`
}
