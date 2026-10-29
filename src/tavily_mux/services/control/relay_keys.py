from sqlalchemy import select
from sqlalchemy.orm import Session

from tavily_mux.common.security import SecretManager, generate_relay_key
from tavily_mux.persistence.models import RelayKey
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.services.control.models import (
    RelayKeyCreated,
    RelayKeyResponse,
    RelayKeyUpdate,
)
from tavily_mux.services.control.shared import require_pool
from tavily_mux.services.errors import NotFoundError


def list_relay_keys(session: Session, pool_id: str) -> list[RelayKeyResponse]:
    require_pool(session, pool_id)
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
    require_pool(session, pool_id)
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
        raise NotFoundError("Relay key not found")
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
        raise NotFoundError("Relay key not found")
    session.delete(relay)
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
