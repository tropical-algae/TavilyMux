import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    base_url: str
    http_proxy: str | None
    https_proxy: str | None
    allow_direct_fallback: bool
    timeout_seconds: float


@dataclass(slots=True)
class RelayRuntime:
    id: str
    pool_id: str
    secret_hash: str
    enabled: bool
    last_used_at: datetime | None = None


@dataclass(slots=True)
class KeyRuntime:
    id: str
    pool_id: str
    name: str
    api_key: str
    enabled: bool
    status: str
    usage: int | None
    usage_limit: int | None
    account_plan: str | None
    account_plan_usage: int | None
    account_plan_limit: int | None
    paygo_usage: int | None
    paygo_limit: int | None
    synced_remaining: int | None
    cooldown_until: datetime | None
    last_checked_at: datetime | None
    last_used_at: datetime | None
    request_count: int
    success_count: int
    failure_count: int
    last_error: str | None
    inflight: int = 0
    inflight_credits: int = 0
    local_consumed: int = 0
    rate_limit_cooldowns: dict[str, datetime] = field(default_factory=dict)

    @property
    def remaining(self) -> int | None:
        if self.synced_remaining is None:
            return None
        return max(
            self.synced_remaining - self.local_consumed - self.inflight_credits,
            0,
        )


@dataclass(slots=True)
class PoolRuntime:
    id: str
    name: str
    enabled: bool
    strategy: str
    monitor_interval_seconds: int
    max_attempts: int
    concurrency_limit: int | None
    rpm_limit: int | None
    profile: ConnectionProfile
    keys: dict[str, KeyRuntime]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_requests: int = 0
    recent_requests: deque[float] = field(default_factory=deque)


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    pools: dict[str, PoolRuntime]
    relay_keys: dict[str, RelayRuntime]
    generation: int
