import secrets
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tavily_mux.common.security import SecretManager, generate_relay_key
from tavily_mux.domain.enums import RoutingStrategy
from tavily_mux.persistence.models import (
    Pool,
    ProxyRequest,
    RelayKey,
    SystemSettings,
    TavilyKey,
)
from tavily_mux.runtime.registry import ROUTABLE_STATUSES, RuntimeRegistry
from tavily_mux.services.control.models import (
    PoolCreate,
    PoolCreated,
    PoolResponse,
    PoolUpdate,
)
from tavily_mux.services.control.shared import (
    decrypt_optional,
    key_is_routable,
    key_quota,
    mask_proxy,
    pool_status,
)
from tavily_mux.services.errors import ConflictError, NotFoundError, NotInitializedError


def list_pools(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry | None = None,
) -> list[PoolResponse]:
    global_settings = _global_settings(session)
    pool_rows = session.scalars(select(Pool).order_by(Pool.created_at.desc())).all()
    key_rows = session.scalars(select(TavilyKey)).all()
    keys_by_pool: dict[str, list[TavilyKey]] = {}
    for key in key_rows:
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
        for pool in pool_rows
    ]


def get_pool(
    session: Session,
    secrets_manager: SecretManager,
    pool_id: str,
    runtime: RuntimeRegistry | None = None,
) -> PoolResponse:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise NotFoundError("Pool not found")
    global_settings = _global_settings(session)
    key_rows = list(
        session.scalars(select(TavilyKey).where(TavilyKey.pool_id == pool_id)).all()
    )
    return _pool_response(
        pool,
        key_rows,
        secrets_manager,
        global_settings,
        _pool_request_metrics(session, pool_id=pool_id).get(pool_id, (0, 0, None)),
        runtime,
    )


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
        raise ConflictError("Pool name already exists") from error
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
        raise NotFoundError("Pool not found")
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
        raise ConflictError("Pool name already exists") from error
    runtime.load()
    return get_pool(session, secrets_manager, pool_id)


def delete_pool(session: Session, runtime: RuntimeRegistry, pool_id: str) -> None:
    pool = session.get(Pool, pool_id)
    if pool is None:
        raise NotFoundError("Pool not found")
    session.delete(pool)
    session.commit()
    runtime.load()


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
        available_count = sum(key_is_routable(key) for key in key_rows)
        remaining_values = [
            quota.effective_remaining
            for key in key_rows
            if key_is_routable(key)
            and (quota := key_quota(key)).effective_remaining is not None
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
        status=pool_status(pool, key_rows),
        strategy=RoutingStrategy(pool.strategy),
        key_count=len(key_rows),
        available_key_count=available_count,
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
        http_proxy=mask_proxy(decrypt_optional(secrets_manager, pool.http_proxy_encrypted)),
        https_proxy=mask_proxy(decrypt_optional(secrets_manager, pool.https_proxy_encrypted)),
        allow_direct_fallback=pool.allow_direct_fallback,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
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


def _global_settings(session: Session) -> SystemSettings:
    settings = session.get(SystemSettings, 1)
    if settings is None:
        raise NotInitializedError("Settings not initialized")
    return settings
