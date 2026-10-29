export type RoutingStrategy = "max_remaining" | "random"
export type QuotaBottleneck = "unknown" | "key" | "account" | "both"
export type PoolStatus = "normal" | "degraded" | "unavailable" | "disabled"
export type KeyStatus =
  | "unknown"
  | "available"
  | "low_quota"
  | "rate_limited"
  | "exhausted"
  | "invalid"
  | "check_failed"
  | "disabled"

export interface Dashboard {
  pool_count: number
  healthy_pool_count: number
  normal_pool_count: number
  degraded_pool_count: number
  unavailable_pool_count: number
  disabled_pool_count: number
  key_count: number
  available_key_count: number
  estimated_remaining: number | null
  requests_today: number
  successes_today: number
  credits_today: number | null
  success_rate: number
  average_latency_ms: number | null
  dropped_log_events: number
  alerts: DashboardAlert[]
}

export interface DashboardAlert {
  severity: "warning" | "critical"
  code: string
  message: string
  pool_id: string | null
  key_id: string | null
}

export interface SystemSettings {
  upstream_base_url: string
  http_proxy: string | null
  https_proxy: string | null
  allow_direct_fallback: boolean
  monitor_interval_seconds: number
  request_timeout_seconds: number
  max_attempts: number
  log_retention_days: number
}

export interface ConnectionTest {
  ok: boolean
  latency_ms: number
  status_code: number | null
  proxy_configured: boolean
  message: string
}

export interface Pool {
  id: string
  name: string
  description: string | null
  enabled: boolean
  status: PoolStatus
  strategy: RoutingStrategy
  key_count: number
  available_key_count: number
  estimated_remaining: number | null
  requests_today: number
  success_rate_today: number
  last_used_at: string | null
  monitor_interval_seconds: number
  max_attempts: number
  concurrency_limit: number | null
  rpm_limit: number | null
  upstream_base_url: string | null
  http_proxy: string | null
  https_proxy: string | null
  allow_direct_fallback: boolean | null
  created_at: string
  updated_at: string
}

export interface CreatedPool extends Pool {
  relay_key: string
}

export interface RelayKey {
  id: string
  name: string
  prefix: string
  enabled: boolean
  created_at: string
  last_used_at: string | null
}

export interface CreatedRelayKey extends RelayKey {
  relay_key: string
}

export interface TavilyKey {
  id: string
  name: string
  masked_key: string
  enabled: boolean
  status: KeyStatus
  usage: number | null
  usage_limit: number | null
  key_remaining: number | null
  account_plan_remaining: number | null
  paygo_remaining: number | null
  account_remaining: number | null
  estimated_remaining: number | null
  quota_bottleneck: QuotaBottleneck
  account_plan: string | null
  account_plan_usage: number | null
  account_plan_limit: number | null
  paygo_usage: number | null
  paygo_limit: number | null
  cooldown_until: string | null
  last_checked_at: string | null
  last_used_at: string | null
  request_count: number
  success_count: number
  failure_count: number
  last_error: string | null
  created_at: string
}

export interface UsageSnapshot {
  captured_at: string
  usage: number | null
  usage_limit: number | null
  account_plan_usage: number | null
  account_plan_limit: number | null
  paygo_usage: number | null
  paygo_limit: number | null
  key_remaining: number | null
  account_plan_remaining: number | null
  paygo_remaining: number | null
  account_remaining: number | null
  estimated_remaining: number | null
  quota_bottleneck: QuotaBottleneck
  status: KeyStatus
}

export interface ProxyAttempt {
  attempt_no: number
  key_id: string | null
  status_code: number | null
  latency_ms: number | null
  error_type: string | null
}

export interface ProxyLog {
  id: string
  pool_id: string | null
  final_key_id: string | null
  created_at: string
  completed_at: string | null
  status_code: number | null
  latency_ms: number | null
  attempt_count: number
  method: string
  endpoint: string
  path: string
  credits: number | null
  error_type: string | null
  external_request_id: string | null
  attempts: ProxyAttempt[]
}

export interface PaginatedLogs {
  items: ProxyLog[]
  total: number
  page: number
  page_size: number
}
