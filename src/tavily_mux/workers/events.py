from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ProxyAttemptEvent:
    attempt_no: int
    key_id: str
    status_code: int | None
    latency_ms: float
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class KeyStateEvent:
    key_id: str
    status: str
    last_used_at: datetime | None
    cooldown_until: datetime | None
    rate_limit_cooldowns: dict[str, datetime]
    request_count: int
    success_count: int
    failure_count: int
    last_error: str | None


@dataclass(frozen=True, slots=True)
class ProxyRequestEvent:
    request_id: str
    pool_id: str
    relay_id: str
    method: str
    endpoint: str
    path: str
    created_at: datetime
    completed_at: datetime
    status_code: int | None
    latency_ms: float
    final_key_id: str | None
    error_type: str | None
    external_request_id: str | None
    credits: int | None
    attempts: tuple[ProxyAttemptEvent, ...]
    key_states: tuple[KeyStateEvent, ...] = field(default_factory=tuple)
