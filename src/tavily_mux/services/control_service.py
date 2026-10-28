import secrets
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tavily_mux.api.control_plane.schemas import (
    DashboardAlert,
    DashboardResponse,
    PaginatedLogs,
    PoolCreate,
    PoolCreated,
    PoolResponse,
    PoolUpdate,
    ProxyAttemptResponse,
    ProxyLogResponse,
    RelayKeyCreated,
    RelayKeyResponse,
    RelayKeyUpdate,
    SettingsResponse,
    SettingsUpdate,
    TavilyKeyCreate,
    TavilyKeyResponse,
    TavilyKeyUpdate,
    UsageSnapshotResponse,
)
from tavily_mux.common.security import SecretManager, generate_relay_key
from tavily_mux.domain.enums import KeyStatus, RoutingStrategy
from tavily_mux.domain.quota import QuotaState, calculate_quota
from tavily_mux.persistence.models import (
    Pool,
    ProxyAttempt,
    ProxyRequest,
    RelayKey,
    SystemSettings,
    TavilyKey,
    UsageSnapshot,
)
from tavily_mux.runtime.models import ConnectionProfile, KeyRuntime
from tavily_mux.runtime.registry import ROUTABLE_STATUSES, RuntimeRegistry


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


def _decrypt_optional(secrets_manager: SecretManager, value: str | None) -> str | None:
    return secrets_manager.decrypt(value) if value else None


def _quota(
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


def _key_quota(key: TavilyKey) -> QuotaState:
    return _quota(
        usage=key.usage,
        usage_limit=key.usage_limit,
        account_plan_usage=key.account_plan_usage,
        account_plan_limit=key.account_plan_limit,
        paygo_usage=key.paygo_usage,
        paygo_limit=key.paygo_limit,
    )


def _key_is_routable(key: TavilyKey) -> bool:
    return (
        key.enabled
        and key.status in ROUTABLE_STATUSES
        and _key_quota(key).effective_remaining != 0
    )


def _usage_snapshot_response(item: UsageSnapshot) -> UsageSnapshotResponse:
    quota = _quota(
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


def get_settings_response(
    session: Session,
    secrets_manager: SecretManager,
) -> SettingsResponse:
    settings = session.get(SystemSettings, 1)
    if settings is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Settings not initialized")
    return SettingsResponse(
        upstream_base_url=settings.upstream_base_url,
        http_proxy=mask_proxy(
            _decrypt_optional(secrets_manager, settings.http_proxy_encrypted)
        ),
        https_proxy=mask_proxy(
            _decrypt_optional(secrets_manager, settings.https_proxy_encrypted)
        ),
        allow_direct_fallback=settings.allow_direct_fallback,
        monitor_interval_seconds=settings.monitor_interval_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        max_attempts=settings.max_attempts,
        log_retention_days=settings.log_retention_days,
    )


def get_connection_profile(
    session: Session,
    secrets_manager: SecretManager,
) -> ConnectionProfile:
    settings = session.get(SystemSettings, 1)
    if settings is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Settings not initialized")
    return ConnectionProfile(
        base_url=settings.upstream_base_url,
        http_proxy=_decrypt_optional(secrets_manager, settings.http_proxy_encrypted),
        https_proxy=_decrypt_optional(secrets_manager, settings.https_proxy_encrypted),
        allow_direct_fallback=settings.allow_direct_fallback,
        timeout_seconds=settings.request_timeout_seconds,
    )


def update_settings(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    payload: SettingsUpdate,
) -> SettingsResponse:
    settings = session.get(SystemSettings, 1)
    if settings is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Settings not initialized")
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field == "http_proxy":
            settings.http_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        elif field == "https_proxy":
            settings.https_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        elif value is not None:
            setattr(settings, field, value)
    session.commit()
    runtime.load()
    return get_settings_response(session, secrets_manager)


def _pool_status(pool: Pool, key_rows: list[TavilyKey]) -> str:
    if not pool.enabled:
        return "disabled"
    available = sum(_key_is_routable(key) for key in key_rows)
    if available == 0:
        return "unavailable"
    if available < len(key_rows):
        return "degraded"
    return "normal"


def _pool_response(
    pool: Pool,
    key_rows: list[TavilyKey],
    secrets_manager: SecretManager,
    global_settings: SystemSettings,
    request_metrics: tuple[int, int, datetime | None] = (0, 0, None),
    runtime: RuntimeRegistry | None = None,
) -> PoolResponse:
    runtime_pool = runtime.snapshot.pools.get(pool.id) if runtime is not None else None
    if runtime_pool is None:
        available_count = sum(_key_is_routable(key) for key in key_rows)
        remaining_values = [
            quota.effective_remaining
            for key in key_rows
            if _key_is_routable(key)
            and (quota := _key_quota(key)).effective_remaining is not None
        ]
    else:
        available_runtime = [
            key
            for key in runtime_pool.keys.values()
            if key.enabled and key.status in ROUTABLE_STATUSES and key.remaining != 0
        ]
        available_count = len(available_runtime)
        remaining_values = [
            remaining for key in available_runtime if (remaining := key.remaining) is not None
        ]
    requests_today, successes_today, last_used_at = request_metrics
    return PoolResponse(
        id=pool.id,
        name=pool.name,
        description=pool.description,
        enabled=pool.enabled,
        status=_pool_status(pool, key_rows),
        strategy=RoutingStrategy(pool.strategy),
        key_count=len(key_rows),
        available_key_count=available_count,
        # Account quota may be shared by several keys. A maximum is safe routing
        # headroom; summing per-key values would report shared capacity repeatedly.
        estimated_remaining=max(remaining_values) if remaining_values else None,
        requests_today=requests_today,
        success_rate_today=(successes_today / requests_today * 100 if requests_today else 0),
        last_used_at=last_used_at,
        monitor_interval_seconds=(
            pool.monitor_interval_seconds or global_settings.monitor_interval_seconds
        ),
        max_attempts=pool.max_attempts or global_settings.max_attempts,
        concurrency_limit=pool.concurrency_limit,
        rpm_limit=pool.rpm_limit,
        upstream_base_url=pool.upstream_base_url,
        http_proxy=mask_proxy(_decrypt_optional(secrets_manager, pool.http_proxy_encrypted)),
        https_proxy=mask_proxy(_decrypt_optional(secrets_manager, pool.https_proxy_encrypted)),
        allow_direct_fallback=pool.allow_direct_fallback,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
    )


def list_pools(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry | None = None,
) -> list[PoolResponse]:
    global_settings = session.get(SystemSettings, 1)
    if global_settings is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Settings not initialized")
    pools = session.scalars(select(Pool).order_by(Pool.created_at.desc())).all()
    keys = session.scalars(select(TavilyKey)).all()
    keys_by_pool: dict[str, list[TavilyKey]] = {}
    for key in keys:
        keys_by_pool.setdefault(key.pool_id, []).append(key)
    request_metrics = _pool_request_metrics(session)
    return [
        _pool_response(
            pool,
            keys_by_pool.get(pool.id, []),
            secrets_manager,
            global_settings,
            request_metrics.get(pool.id, (0, 0, None)),
            runtime,
        )
        for pool in pools
    ]


def get_pool(
    session: Session,
    secrets_manager: SecretManager,
    pool_id: str,
    runtime: RuntimeRegistry | None = None,
) -> PoolResponse:
    pool = session.get(Pool, pool_id)
    global_settings = session.get(SystemSettings, 1)
    if pool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pool not found")
    if global_settings is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Settings not initialized")
    keys = list(session.scalars(select(TavilyKey).where(TavilyKey.pool_id == pool_id)).all())
    return _pool_response(
        pool,
        keys,
        secrets_manager,
        global_settings,
        _pool_request_metrics(session, pool_id=pool_id).get(pool_id, (0, 0, None)),
        runtime,
    )


def _pool_request_metrics(
    session: Session,
    *,
    pool_id: str | None = None,
) -> dict[str, tuple[int, int, datetime | None]]:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    query = select(
        ProxyRequest.pool_id,
        func.sum(case((ProxyRequest.created_at >= today, 1), else_=0)),
        func.sum(
            case(
                (
                    and_(
                        ProxyRequest.created_at >= today,
                        ProxyRequest.status_code.between(200, 299),
                    ),
                    1,
                ),
                else_=0,
            )
        ),
        func.max(ProxyRequest.created_at),
    ).where(ProxyRequest.pool_id.is_not(None))
    if pool_id is not None:
        query = query.where(ProxyRequest.pool_id == pool_id)
    rows = session.execute(query.group_by(ProxyRequest.pool_id)).all()
    return {
        current_pool_id: (
            int(requests_today or 0),
            int(successes_today or 0),
            last_used_at,
        )
        for current_pool_id, requests_today, successes_today, last_used_at in rows
        if current_pool_id is not None
    }


def create_pool(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    payload: PoolCreate,
) -> PoolCreated:
    pool_id = secrets.token_hex(12)
    pool = Pool(
        id=pool_id,
        name=payload.name,
        description=payload.description,
        strategy=payload.strategy.value,
        monitor_interval_seconds=payload.monitor_interval_seconds,
        max_attempts=payload.max_attempts,
        concurrency_limit=payload.concurrency_limit,
        rpm_limit=payload.rpm_limit,
        upstream_base_url=payload.upstream_base_url,
        http_proxy_encrypted=(
            secrets_manager.encrypt(payload.http_proxy) if payload.http_proxy else None
        ),
        https_proxy_encrypted=(
            secrets_manager.encrypt(payload.https_proxy) if payload.https_proxy else None
        ),
        allow_direct_fallback=payload.allow_direct_fallback,
    )
    relay_id, relay_secret, token = generate_relay_key()
    relay = RelayKey(
        id=relay_id,
        pool_id=pool_id,
        name="default",
        secret_hash=secrets_manager.digest(relay_secret, purpose="relay-key"),
    )
    session.add_all([pool, relay])
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Pool name already exists") from error
    session.refresh(pool)
    runtime.load()
    response = get_pool(session, secrets_manager, pool_id)
    return PoolCreated(**response.model_dump(), relay_key=token)


def update_pool(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
    payload: PoolUpdate,
) -> PoolResponse:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pool not found")
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field == "strategy" and value is not None:
            pool.strategy = value.value
        elif field == "http_proxy":
            pool.http_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        elif field == "https_proxy":
            pool.https_proxy_encrypted = secrets_manager.encrypt(value) if value else None
        else:
            setattr(pool, field, value)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Pool name already exists") from error
    runtime.load()
    return get_pool(session, secrets_manager, pool_id)


def delete_pool(session: Session, runtime: RuntimeRegistry, pool_id: str) -> None:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pool not found")
    session.delete(pool)
    session.commit()
    runtime.load()


def _relay_response(relay: RelayKey) -> RelayKeyResponse:
    return RelayKeyResponse(
        id=relay.id,
        name=relay.name,
        prefix=f"tpool_{relay.id}",
        enabled=relay.enabled,
        created_at=relay.created_at,
        last_used_at=relay.last_used_at,
    )


def list_relay_keys(session: Session, pool_id: str) -> list[RelayKeyResponse]:
    _require_pool(session, pool_id)
    rows = session.scalars(
        select(RelayKey).where(RelayKey.pool_id == pool_id).order_by(RelayKey.created_at.desc())
    ).all()
    return [_relay_response(row) for row in rows]


def create_relay_key(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
    name: str,
) -> RelayKeyCreated:
    _require_pool(session, pool_id)
    relay_id, relay_secret, token = generate_relay_key()
    relay = RelayKey(
        id=relay_id,
        pool_id=pool_id,
        name=name.strip(),
        secret_hash=secrets_manager.digest(relay_secret, purpose="relay-key"),
    )
    session.add(relay)
    session.commit()
    session.refresh(relay)
    runtime.load()
    return RelayKeyCreated(**_relay_response(relay).model_dump(), relay_key=token)


def update_relay_key(
    session: Session,
    runtime: RuntimeRegistry,
    pool_id: str,
    relay_id: str,
    payload: RelayKeyUpdate,
) -> RelayKeyResponse:
    relay = session.get(RelayKey, relay_id)
    if relay is None or relay.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relay key not found")
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is not None:
            setattr(relay, field, value)
    session.commit()
    runtime.load()
    return _relay_response(relay)


def delete_relay_key(
    session: Session,
    runtime: RuntimeRegistry,
    pool_id: str,
    relay_id: str,
) -> None:
    relay = session.get(RelayKey, relay_id)
    if relay is None or relay.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relay key not found")
    session.delete(relay)
    session.commit()
    runtime.load()


def _key_response(
    key: TavilyKey,
    secrets_manager: SecretManager,
    runtime_key: KeyRuntime | None = None,
) -> TavilyKeyResponse:
    plain = secrets_manager.decrypt(key.encrypted_key)
    quota = _key_quota(key)
    return TavilyKeyResponse(
        id=key.id,
        name=key.name,
        masked_key=mask_secret(plain),
        enabled=key.enabled,
        status=KeyStatus(runtime_key.status if runtime_key is not None else key.status),
        usage=key.usage,
        usage_limit=key.usage_limit,
        key_remaining=quota.key_remaining,
        account_plan_remaining=quota.account_plan_remaining,
        paygo_remaining=quota.paygo_remaining,
        account_remaining=quota.account_remaining,
        estimated_remaining=(
            runtime_key.remaining if runtime_key is not None else quota.effective_remaining
        ),
        quota_bottleneck=quota.bottleneck,
        account_plan=key.account_plan,
        account_plan_usage=key.account_plan_usage,
        account_plan_limit=key.account_plan_limit,
        paygo_usage=key.paygo_usage,
        paygo_limit=key.paygo_limit,
        cooldown_until=(
            runtime_key.cooldown_until if runtime_key is not None else key.cooldown_until
        ),
        last_checked_at=key.last_checked_at,
        last_used_at=(
            runtime_key.last_used_at if runtime_key is not None else key.last_used_at
        ),
        request_count=(
            runtime_key.request_count if runtime_key is not None else key.request_count
        ),
        success_count=(
            runtime_key.success_count if runtime_key is not None else key.success_count
        ),
        failure_count=(
            runtime_key.failure_count if runtime_key is not None else key.failure_count
        ),
        last_error=(runtime_key.last_error if runtime_key is not None else key.last_error),
        created_at=key.created_at,
    )


def list_tavily_keys(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
) -> list[TavilyKeyResponse]:
    _require_pool(session, pool_id)
    rows = session.scalars(
        select(TavilyKey)
        .where(TavilyKey.pool_id == pool_id)
        .order_by(TavilyKey.created_at.asc())
    ).all()
    runtime_pool = runtime.snapshot.pools.get(pool_id)
    return [
        _key_response(
            row,
            secrets_manager,
            runtime_pool.keys.get(row.id) if runtime_pool is not None else None,
        )
        for row in rows
    ]


def get_tavily_key(
    session: Session,
    secrets_manager: SecretManager,
    pool_id: str,
    key_id: str,
    runtime: RuntimeRegistry | None = None,
) -> TavilyKeyResponse:
    row = session.get(TavilyKey, key_id)
    if row is None or row.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tavily key not found")
    runtime_pool = runtime.snapshot.pools.get(pool_id) if runtime is not None else None
    return _key_response(
        row,
        secrets_manager,
        runtime_pool.keys.get(key_id) if runtime_pool is not None else None,
    )


def create_tavily_key(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
    payload: TavilyKeyCreate,
) -> TavilyKeyResponse:
    _require_pool(session, pool_id)
    key_value = payload.api_key.strip()
    fingerprint = secrets_manager.digest(key_value, purpose="tavily-key")
    _raise_for_existing_key(session, fingerprint)
    row = TavilyKey(
        id=secrets.token_hex(12),
        pool_id=pool_id,
        name=payload.name.strip(),
        encrypted_key=secrets_manager.encrypt(key_value),
        fingerprint=fingerprint,
        status=KeyStatus.UNKNOWN.value,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tavily key already exists") from error
    session.refresh(row)
    runtime.load()
    return _key_response(row, secrets_manager)


def create_tavily_keys(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
    payloads: list[TavilyKeyCreate],
) -> list[TavilyKeyResponse]:
    _require_pool(session, pool_id)
    rows: list[TavilyKey] = []
    seen: set[str] = set()
    for payload in payloads:
        key_value = payload.api_key.strip()
        fingerprint = secrets_manager.digest(key_value, purpose="tavily-key")
        if fingerprint in seen:
            raise HTTPException(status.HTTP_409_CONFLICT, "Duplicate Tavily key in request")
        seen.add(fingerprint)
        _raise_for_existing_key(session, fingerprint)
        rows.append(
            TavilyKey(
                id=secrets.token_hex(12),
                pool_id=pool_id,
                name=payload.name.strip(),
                encrypted_key=secrets_manager.encrypt(key_value),
                fingerprint=fingerprint,
                status=KeyStatus.UNKNOWN.value,
            )
        )
    session.add_all(rows)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tavily key already exists") from error
    for row in rows:
        session.refresh(row)
    runtime.load()
    return [_key_response(row, secrets_manager) for row in rows]


def _raise_for_existing_key(session: Session, fingerprint: str) -> None:
    existing = session.scalar(select(TavilyKey).where(TavilyKey.fingerprint == fingerprint))
    if existing is None:
        return
    pool = session.get(Pool, existing.pool_id)
    pool_name = pool.name if pool is not None else existing.pool_id
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f'Tavily key already exists in pool "{pool_name}"',
    )


def update_tavily_key(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
    key_id: str,
    payload: TavilyKeyUpdate,
) -> TavilyKeyResponse:
    row = session.get(TavilyKey, key_id)
    if row is None or row.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tavily key not found")
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    if payload.enabled is False:
        row.status = KeyStatus.DISABLED.value
    elif payload.enabled is True and row.status == KeyStatus.DISABLED.value:
        row.status = KeyStatus.UNKNOWN.value
    session.commit()
    runtime.load()
    return _key_response(row, secrets_manager)


def delete_tavily_key(
    session: Session,
    runtime: RuntimeRegistry,
    pool_id: str,
    key_id: str,
) -> None:
    row = session.get(TavilyKey, key_id)
    if row is None or row.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tavily key not found")
    session.delete(row)
    session.commit()
    runtime.load()


def dashboard(
    session: Session,
    *,
    dropped_log_events: int = 0,
    runtime: RuntimeRegistry | None = None,
) -> DashboardResponse:
    pools = session.scalars(select(Pool)).all()
    keys = session.scalars(select(TavilyKey)).all()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    requests_today = (
        session.scalar(
            select(func.count())
            .select_from(ProxyRequest)
            .where(ProxyRequest.created_at >= today)
        )
        or 0
    )
    successes_today = (
        session.scalar(
            select(func.count())
            .select_from(ProxyRequest)
            .where(ProxyRequest.created_at >= today, ProxyRequest.status_code.between(200, 299))
        )
        or 0
    )
    average_latency = session.scalar(
        select(func.avg(ProxyRequest.latency_ms)).where(ProxyRequest.created_at >= today)
    )
    credits_today = session.scalar(
        select(func.sum(ProxyRequest.credits)).where(ProxyRequest.created_at >= today)
    )
    keys_by_pool: dict[str, list[TavilyKey]] = {}
    for key in keys:
        keys_by_pool.setdefault(key.pool_id, []).append(key)
    pool_statuses = {
        pool.id: _pool_status(pool, keys_by_pool.get(pool.id, [])) for pool in pools
    }
    healthy_pool_count = sum(
        current in {"normal", "degraded"} for current in pool_statuses.values()
    )
    if runtime is None:
        available_key_count = sum(_key_is_routable(key) for key in keys)
        remaining_values = [
            quota.effective_remaining
            for key in keys
            if _key_is_routable(key)
            and (quota := _key_quota(key)).effective_remaining is not None
        ]
    else:
        runtime_keys = [
            key for pool in runtime.snapshot.pools.values() for key in pool.keys.values()
        ]
        available_runtime = [
            key
            for key in runtime_keys
            if key.enabled and key.status in ROUTABLE_STATUSES and key.remaining != 0
        ]
        available_key_count = len(available_runtime)
        remaining_values = [
            remaining for key in available_runtime if (remaining := key.remaining) is not None
        ]
    alerts = [
        DashboardAlert(
            severity="critical",
            code="pool_unavailable",
            message=f"账号池“{pool.name}”当前没有可用 Key",
            pool_id=pool.id,
        )
        for pool in pools
        if pool_statuses[pool.id] == "unavailable"
    ]
    alert_statuses = {
        KeyStatus.INVALID.value: ("critical", "key_invalid", "鉴权失败"),
        KeyStatus.EXHAUSTED.value: ("critical", "key_exhausted", "额度已耗尽"),
        KeyStatus.RATE_LIMITED.value: ("warning", "key_rate_limited", "正在被限流"),
        KeyStatus.LOW_QUOTA.value: ("warning", "key_low_quota", "剩余额度偏低"),
        KeyStatus.CHECK_FAILED.value: ("warning", "key_check_failed", "额度检测失败"),
    }
    for key in keys:
        alert = alert_statuses.get(key.status)
        if key.enabled and alert is not None:
            severity, code, description = alert
            alerts.append(
                DashboardAlert(
                    severity=severity,
                    code=code,
                    message=f"Tavily Key“{key.name}”{description}",
                    pool_id=key.pool_id,
                    key_id=key.id,
                )
            )
    if dropped_log_events:
        alerts.insert(
            0,
            DashboardAlert(
                severity="critical",
                code="request_logs_dropped",
                message=f"事件队列已丢弃 {dropped_log_events} 条请求日志",
            ),
        )
    return DashboardResponse(
        pool_count=len(pools),
        healthy_pool_count=healthy_pool_count,
        normal_pool_count=sum(status == "normal" for status in pool_statuses.values()),
        degraded_pool_count=sum(status == "degraded" for status in pool_statuses.values()),
        unavailable_pool_count=sum(
            status == "unavailable" for status in pool_statuses.values()
        ),
        disabled_pool_count=sum(status == "disabled" for status in pool_statuses.values()),
        key_count=len(keys),
        available_key_count=available_key_count,
        estimated_remaining=max(remaining_values) if remaining_values else None,
        requests_today=requests_today,
        successes_today=successes_today,
        credits_today=int(credits_today) if credits_today is not None else None,
        success_rate=(successes_today / requests_today * 100 if requests_today else 0),
        average_latency_ms=float(average_latency) if average_latency is not None else None,
        dropped_log_events=dropped_log_events,
        alerts=alerts[:20],
    )


def list_usage_snapshots(
    session: Session,
    pool_id: str,
    key_id: str,
    *,
    limit: int,
) -> list[UsageSnapshotResponse]:
    row = session.get(TavilyKey, key_id)
    if row is None or row.pool_id != pool_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tavily key not found")
    snapshots = session.scalars(
        select(UsageSnapshot)
        .where(UsageSnapshot.key_id == key_id)
        .order_by(UsageSnapshot.captured_at.desc())
        .limit(limit)
    ).all()
    return [_usage_snapshot_response(item) for item in reversed(snapshots)]


def list_proxy_logs(
    session: Session,
    *,
    page: int,
    page_size: int,
    pool_id: str | None,
    status_code: int | None,
    key_id: str | None = None,
    success: bool | None = None,
    retried: bool | None = None,
    request_id: str | None = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
) -> PaginatedLogs:
    filters = []
    if pool_id is not None:
        filters.append(ProxyRequest.pool_id == pool_id)
    if status_code is not None:
        filters.append(ProxyRequest.status_code == status_code)
    if key_id is not None:
        filters.append(
            ProxyRequest.id.in_(
                select(ProxyAttempt.request_id).where(ProxyAttempt.key_id == key_id)
            )
        )
    if success is True:
        filters.append(ProxyRequest.status_code.between(200, 299))
    elif success is False:
        filters.append(
            or_(
                ProxyRequest.status_code.is_(None),
                ProxyRequest.status_code < 200,
                ProxyRequest.status_code >= 300,
            )
        )
    if retried is True:
        filters.append(ProxyRequest.attempt_count > 1)
    elif retried is False:
        filters.append(ProxyRequest.attempt_count <= 1)
    if request_id:
        pattern = f"%{request_id.strip()}%"
        filters.append(
            or_(
                ProxyRequest.id.ilike(pattern),
                ProxyRequest.external_request_id.ilike(pattern),
            )
        )
    if time_from is not None:
        filters.append(ProxyRequest.created_at >= time_from)
    if time_to is not None:
        filters.append(ProxyRequest.created_at <= time_to)
    total = session.scalar(select(func.count()).select_from(ProxyRequest).where(*filters)) or 0
    requests = session.scalars(
        select(ProxyRequest)
        .where(*filters)
        .order_by(ProxyRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    request_ids = [request.id for request in requests]
    attempts_by_request: dict[str, list[ProxyAttemptResponse]] = {}
    if request_ids:
        attempts = session.scalars(
            select(ProxyAttempt)
            .where(ProxyAttempt.request_id.in_(request_ids))
            .order_by(ProxyAttempt.request_id, ProxyAttempt.attempt_no)
        ).all()
        for attempt in attempts:
            attempts_by_request.setdefault(attempt.request_id, []).append(
                ProxyAttemptResponse(
                    attempt_no=attempt.attempt_no,
                    key_id=attempt.key_id,
                    status_code=attempt.status_code,
                    latency_ms=attempt.latency_ms,
                    error_type=attempt.error_type,
                )
            )
    items = [
        ProxyLogResponse(
            id=request.id,
            pool_id=request.pool_id,
            final_key_id=request.final_key_id,
            created_at=request.created_at,
            completed_at=request.completed_at,
            status_code=request.status_code,
            latency_ms=request.latency_ms,
            attempt_count=request.attempt_count,
            credits=request.credits,
            error_type=request.error_type,
            external_request_id=request.external_request_id,
            attempts=attempts_by_request.get(request.id, []),
        )
        for request in requests
    ]
    return PaginatedLogs(items=items, total=total, page=page, page_size=page_size)


def _require_pool(session: Session, pool_id: str) -> Pool:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pool not found")
    return pool
