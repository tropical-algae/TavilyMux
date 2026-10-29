from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from tavily_mux.common.security import SecretManager
from tavily_mux.domain.enums import KeyStatus
from tavily_mux.domain.quota import QuotaState, calculate_quota
from tavily_mux.persistence.models import Pool, TavilyKey, UsageSnapshot
from tavily_mux.runtime.registry import ROUTABLE_STATUSES
from tavily_mux.services.control.models import UsageSnapshotResponse
from tavily_mux.services.errors import NotFoundError


def mask_secret(value: str) -> str:
    if len(value) <= 12:
        return "****"
    return f"{value[:8]}••••{value[-4:]}"


def mask_proxy(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.username is None:
        return value
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{parsed.username}:••••@{hostname}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def decrypt_optional(secrets_manager: SecretManager, value: str | None) -> str | None:
    return secrets_manager.decrypt(value) if value else None


def calculate_stored_quota(
    *,
    usage: int | None,
    usage_limit: int | None,
    account_plan_usage: int | None,
    account_plan_limit: int | None,
    paygo_usage: int | None,
    paygo_limit: int | None,
) -> QuotaState:
    return calculate_quota(
        key_usage=usage,
        key_limit=usage_limit,
        account_plan_usage=account_plan_usage,
        account_plan_limit=account_plan_limit,
        paygo_usage=paygo_usage,
        paygo_limit=paygo_limit,
    )


def key_quota(key: TavilyKey) -> QuotaState:
    return calculate_stored_quota(
        usage=key.usage,
        usage_limit=key.usage_limit,
        account_plan_usage=key.account_plan_usage,
        account_plan_limit=key.account_plan_limit,
        paygo_usage=key.paygo_usage,
        paygo_limit=key.paygo_limit,
    )


def key_is_routable(key: TavilyKey) -> bool:
    return (
        key.enabled
        and key.status in ROUTABLE_STATUSES
        and key_quota(key).effective_remaining != 0
    )


def pool_status(pool: Pool, key_rows: list[TavilyKey]) -> str:
    if not pool.enabled:
        return "disabled"
    available = sum(key_is_routable(key) for key in key_rows)
    if available == 0:
        return "unavailable"
    if available < len(key_rows):
        return "degraded"
    return "normal"


def usage_snapshot_response(item: UsageSnapshot) -> UsageSnapshotResponse:
    quota = calculate_stored_quota(
        usage=item.usage,
        usage_limit=item.usage_limit,
        account_plan_usage=item.account_plan_usage,
        account_plan_limit=item.account_plan_limit,
        paygo_usage=item.paygo_usage,
        paygo_limit=item.paygo_limit,
    )
    return UsageSnapshotResponse(
        captured_at=item.captured_at,
        usage=item.usage,
        usage_limit=item.usage_limit,
        account_plan_usage=item.account_plan_usage,
        account_plan_limit=item.account_plan_limit,
        paygo_usage=item.paygo_usage,
        paygo_limit=item.paygo_limit,
        key_remaining=quota.key_remaining,
        account_plan_remaining=quota.account_plan_remaining,
        paygo_remaining=quota.paygo_remaining,
        account_remaining=quota.account_remaining,
        estimated_remaining=quota.effective_remaining,
        quota_bottleneck=quota.bottleneck,
        status=KeyStatus(item.status),
    )


def require_pool(session: Session, pool_id: str) -> Pool:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise NotFoundError("Pool not found")
    return pool
