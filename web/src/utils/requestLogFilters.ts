import type { RequestLogApiParams, RequestLogFilters } from "../types/requestLogs"

type QuerySource = Record<string, unknown>

const DEFAULT_PAGE_SIZE = 50
const QUERY_FIELDS = [
  "pool_id",
  "key_id",
  "status_code",
  "success",
  "retried",
  "request_id",
  "time_from",
  "time_to",
  "page",
] as const

export function createRequestLogFilters(): RequestLogFilters {
  return {
    pool_id: "",
    key_id: "",
    status_code: "",
    success: "",
    retried: "",
    request_id: "",
    time_from: "",
    time_to: "",
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
  }
}

function firstString(value: unknown): string {
  const resolved = Array.isArray(value) ? value[0] : value
  return typeof resolved === "string" ? resolved.trim() : ""
}

function booleanFilter(value: unknown): "" | "true" | "false" {
  const resolved = firstString(value)
  return resolved === "true" || resolved === "false" ? resolved : ""
}

function dateTimeFilter(value: unknown): string {
  const resolved = firstString(value)
  return resolved && !Number.isNaN(new Date(resolved).getTime()) ? resolved : ""
}

function positiveInteger(value: unknown, fallback: number): number {
  const parsed = Number.parseInt(firstString(value), 10)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function parseRequestLogFilters(query: QuerySource): RequestLogFilters {
  const filters = createRequestLogFilters()
  filters.pool_id = firstString(query.pool_id)
  filters.key_id = filters.pool_id ? firstString(query.key_id) : ""
  filters.status_code = /^\d{1,3}$/.test(firstString(query.status_code))
    ? firstString(query.status_code)
    : ""
  filters.success = booleanFilter(query.success)
  filters.retried = booleanFilter(query.retried)
  filters.request_id = firstString(query.request_id).slice(0, 200)
  filters.time_from = dateTimeFilter(query.time_from)
  filters.time_to = dateTimeFilter(query.time_to)
  filters.page = positiveInteger(query.page, 1)
  return filters
}

export function serializeRequestLogFilters(filters: RequestLogFilters): Record<string, string> {
  const query: Record<string, string> = {}
  for (const field of QUERY_FIELDS) {
    const value = filters[field]
    if (field === "page") {
      if (value !== 1) query.page = String(value)
    } else if (value) {
      query[field] = String(value)
    }
  }
  return query
}

function canonicalQuery(query: QuerySource): Record<string, string> {
  const canonical: Record<string, string> = {}
  for (const [key, value] of Object.entries(query).sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    const resolved = firstString(value)
    if (resolved) canonical[key] = resolved
  }
  return canonical
}

export function requestLogQueryMatches(
  query: QuerySource,
  filters: RequestLogFilters,
): boolean {
  return (
    JSON.stringify(canonicalQuery(query)) ===
    JSON.stringify(canonicalQuery(serializeRequestLogFilters(filters)))
  )
}

function optionalBoolean(value: "" | "true" | "false"): boolean | undefined {
  if (!value) return undefined
  return value === "true"
}

function optionalIsoDate(value: string): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

export function toRequestLogApiParams(filters: RequestLogFilters): RequestLogApiParams {
  return {
    page: filters.page,
    page_size: filters.page_size,
    pool_id: filters.pool_id || undefined,
    key_id: filters.key_id || undefined,
    status_code: filters.status_code ? Number(filters.status_code) : undefined,
    success: optionalBoolean(filters.success),
    retried: optionalBoolean(filters.retried),
    request_id: filters.request_id || undefined,
    time_from: optionalIsoDate(filters.time_from),
    time_to: optionalIsoDate(filters.time_to),
  }
}

export function countRequestLogFilters(filters: RequestLogFilters): number {
  return [
    filters.pool_id,
    filters.key_id,
    filters.status_code,
    filters.success,
    filters.retried,
    filters.request_id,
    filters.time_from,
    filters.time_to,
  ].filter(Boolean).length
}
