from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from tavily_mux.domain.enums import KeyStatus, QuotaBottleneck, RoutingStrategy


def _validate_http_url(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError(f"{field_name} must use http:// or https://")
    return normalized


class LoginRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=500)
    remember: bool = False


class LoginResponse(BaseModel):
    authenticated: bool = True
    csrf_token: str


class ChangeAdminSecretRequest(BaseModel):
    current_secret: str = Field(min_length=1, max_length=500)
    new_secret: str = Field(min_length=12, max_length=500)


class AuthStatus(BaseModel):
    authenticated: bool = True


class SettingsResponse(BaseModel):
    upstream_base_url: str
    http_proxy: str | None
    https_proxy: str | None
    allow_direct_fallback: bool
    monitor_interval_seconds: int
    request_timeout_seconds: float
    max_attempts: int
    log_retention_days: int


class SettingsUpdate(BaseModel):
    upstream_base_url: str | None = None
    http_proxy: str | None = None
    https_proxy: str | None = None
    allow_direct_fallback: bool | None = None
    monitor_interval_seconds: int | None = Field(default=None, ge=60, le=86_400)
    request_timeout_seconds: float | None = Field(default=None, ge=1, le=600)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    log_retention_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("upstream_base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="upstream_base_url")

    @field_validator("http_proxy", "https_proxy")
    @classmethod
    def validate_proxy(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="proxy")


class ConnectionTestResponse(BaseModel):
    ok: bool
    latency_ms: float
    status_code: int | None
    proxy_configured: bool
    message: str


class PoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    strategy: RoutingStrategy = RoutingStrategy.MAX_REMAINING
    monitor_interval_seconds: int | None = Field(default=None, ge=60, le=86_400)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    concurrency_limit: int | None = Field(default=None, ge=1, le=100_000)
    rpm_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    upstream_base_url: str | None = None
    http_proxy: str | None = None
    https_proxy: str | None = None
    allow_direct_fallback: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("upstream_base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="upstream_base_url")

    @field_validator("http_proxy", "https_proxy")
    @classmethod
    def validate_proxy(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="proxy")


class PoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    strategy: RoutingStrategy | None = None
    monitor_interval_seconds: int | None = Field(default=None, ge=60, le=86_400)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    concurrency_limit: int | None = Field(default=None, ge=1, le=100_000)
    rpm_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    upstream_base_url: str | None = None
    http_proxy: str | None = None
    https_proxy: str | None = None
    allow_direct_fallback: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("upstream_base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="upstream_base_url")

    @field_validator("http_proxy", "https_proxy")
    @classmethod
    def validate_proxy(cls, value: str | None) -> str | None:
        return _validate_http_url(value, field_name="proxy")


PoolStatus = Literal["normal", "degraded", "unavailable", "disabled"]


class PoolResponse(BaseModel):
    id: str
    name: str
    description: str | None
    enabled: bool
    status: PoolStatus
    strategy: RoutingStrategy
    key_count: int
    available_key_count: int
    estimated_remaining: int | None
    requests_today: int
    success_rate_today: float
    last_used_at: datetime | None
    monitor_interval_seconds: int
    max_attempts: int
    concurrency_limit: int | None
    rpm_limit: int | None
    upstream_base_url: str | None
    http_proxy: str | None
    https_proxy: str | None
    allow_direct_fallback: bool | None
    created_at: datetime
    updated_at: datetime


class PoolCreated(PoolResponse):
    relay_key: str


class RelayKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RelayKeyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None


class RelayKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    enabled: bool
    created_at: datetime
    last_used_at: datetime | None


class RelayKeyCreated(RelayKeyResponse):
    relay_key: str


class TavilyKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=8, max_length=500)


class TavilyKeyBulkCreate(BaseModel):
    keys: list[TavilyKeyCreate] = Field(min_length=1, max_length=100)


class TavilyKeyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None


class TavilyKeyResponse(BaseModel):
    id: str
    name: str
    masked_key: str
    enabled: bool
    status: KeyStatus
    usage: int | None
    usage_limit: int | None
    key_remaining: int | None
    account_plan_remaining: int | None
    paygo_remaining: int | None
    account_remaining: int | None
    estimated_remaining: int | None
    quota_bottleneck: QuotaBottleneck
    account_plan: str | None
    account_plan_usage: int | None
    account_plan_limit: int | None
    paygo_usage: int | None
    paygo_limit: int | None
    cooldown_until: datetime | None
    last_checked_at: datetime | None
    last_used_at: datetime | None
    request_count: int
    success_count: int
    failure_count: int
    last_error: str | None
    created_at: datetime


class UsageSnapshotResponse(BaseModel):
    captured_at: datetime
    usage: int | None
    usage_limit: int | None
    account_plan_usage: int | None
    account_plan_limit: int | None
    paygo_usage: int | None
    paygo_limit: int | None
    key_remaining: int | None
    account_plan_remaining: int | None
    paygo_remaining: int | None
    account_remaining: int | None
    estimated_remaining: int | None
    quota_bottleneck: QuotaBottleneck
    status: KeyStatus


class ProxyAttemptResponse(BaseModel):
    attempt_no: int
    key_id: str | None
    status_code: int | None
    latency_ms: float | None
    error_type: str | None


class ProxyLogResponse(BaseModel):
    id: str
    pool_id: str | None
    final_key_id: str | None
    created_at: datetime
    completed_at: datetime | None
    status_code: int | None
    latency_ms: float | None
    attempt_count: int
    method: str
    endpoint: str
    path: str
    credits: int | None
    error_type: str | None
    external_request_id: str | None
    attempts: list[ProxyAttemptResponse] = Field(default_factory=list)


class PaginatedLogs(BaseModel):
    items: list[ProxyLogResponse]
    total: int
    page: int
    page_size: int


class DashboardAlert(BaseModel):
    severity: Literal["warning", "critical"]
    code: str
    message: str
    pool_id: str | None = None
    key_id: str | None = None


class DashboardResponse(BaseModel):
    pool_count: int
    healthy_pool_count: int
    normal_pool_count: int
    degraded_pool_count: int
    unavailable_pool_count: int
    disabled_pool_count: int
    key_count: int
    available_key_count: int
    estimated_remaining: int | None
    requests_today: int
    successes_today: int
    credits_today: int | None
    success_rate: float
    average_latency_ms: float | None
    dropped_log_events: int
    alerts: list[DashboardAlert]
