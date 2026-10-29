import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tavily_mux.common.security import SecretManager
from tavily_mux.domain.enums import KeyStatus
from tavily_mux.persistence.models import Pool, TavilyKey, UsageSnapshot
from tavily_mux.runtime.models import KeyRuntime
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.services.control.models import (
    TavilyKeyCreate,
    TavilyKeyResponse,
    TavilyKeyUpdate,
    UsageSnapshotResponse,
)
from tavily_mux.services.control.shared import (
    key_quota,
    mask_secret,
    require_pool,
    usage_snapshot_response,
)
from tavily_mux.services.errors import ConflictError, NotFoundError


def list_tavily_keys(
    session: Session,
    secrets_manager: SecretManager,
    runtime: RuntimeRegistry,
    pool_id: str,
) -> list[TavilyKeyResponse]:
    require_pool(session, pool_id)
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
        raise NotFoundError("Tavily key not found")
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
    require_pool(session, pool_id)
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
        raise ConflictError("Tavily key already exists") from error
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
    require_pool(session, pool_id)
    rows: list[TavilyKey] = []
    seen: set[str] = set()
    for payload in payloads:
        key_value = payload.api_key.strip()
        fingerprint = secrets_manager.digest(key_value, purpose="tavily-key")
        if fingerprint in seen:
            raise ConflictError("Duplicate Tavily key in request")
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
        raise ConflictError("Tavily key already exists") from error
    for row in rows:
        session.refresh(row)
    runtime.load()
    return [_key_response(row, secrets_manager) for row in rows]


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
        raise NotFoundError("Tavily key not found")
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
        raise NotFoundError("Tavily key not found")
    session.delete(row)
    session.commit()
    runtime.load()


def list_usage_snapshots(
    session: Session,
    pool_id: str,
    key_id: str,
    *,
    limit: int,
) -> list[UsageSnapshotResponse]:
    row = session.get(TavilyKey, key_id)
    if row is None or row.pool_id != pool_id:
        raise NotFoundError("Tavily key not found")
    snapshots = session.scalars(
        select(UsageSnapshot)
        .where(UsageSnapshot.key_id == key_id)
        .order_by(UsageSnapshot.captured_at.desc())
        .limit(limit)
    ).all()
    return [usage_snapshot_response(item) for item in reversed(snapshots)]


def _key_response(
    key: TavilyKey,
    secrets_manager: SecretManager,
    runtime_key: KeyRuntime | None = None,
) -> TavilyKeyResponse:
    plain = secrets_manager.decrypt(key.encrypted_key)
    quota = key_quota(key)
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


def _raise_for_existing_key(session: Session, fingerprint: str) -> None:
    existing = session.scalar(select(TavilyKey).where(TavilyKey.fingerprint == fingerprint))
    if existing is None:
        return
    pool = session.get(Pool, existing.pool_id)
    pool_name = pool.name if pool is not None else existing.pool_id
    raise ConflictError(f'Tavily key already exists in pool "{pool_name}"')
