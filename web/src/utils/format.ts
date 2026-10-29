import { currentLocale, t } from "../i18n/index.ts"

export function formatDate(value: string | null): string {
  if (!value) return t("common.noRecord")
  return new Intl.DateTimeFormat(currentLocale(), {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value))
}

export function formatNumber(value: number | null): string {
  return value === null ? "—" : new Intl.NumberFormat(currentLocale()).format(value)
}

export function formatLatency(value: number | null): string {
  if (value === null) return "—"
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`
  return `${Math.round(value)} ms`
}

export function successRate(success: number, total: number): string {
  return total === 0 ? "—" : `${Math.round((success / total) * 100)}%`
}
