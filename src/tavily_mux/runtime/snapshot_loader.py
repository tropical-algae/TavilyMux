from collections import deque
from datetime import datetime

from loguru import logger
from sqlalchemy import select

from tavily_mux.common.security import SecretManager
from tavily_mux.domain.quota import calculate_quota
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import (
    Pool,
    RelayKey,
    SystemSettings,
    TaskAffinity,
    TavilyKey,
)
from tavily_mux.runtime.models import (
    ConnectionProfile,
    KeyRuntime,
    PoolRuntime,
    RelayRuntime,
    RuntimeSnapshot,
)


class RuntimeSnapshotLoader:
    """Build registry snapshots from persisted configuration."""

    def __init__(self, database: Database, secrets: SecretManager) -> None:
        self._database = database
        self._secrets = secrets

    def load(self, previous: RuntimeSnapshot) -> RuntimeSnapshot:
        with self._database.session() as session:
            settings = session.get(SystemSettings, 1)
            if settings is None:
                raise RuntimeError("System settings are not initialized")
            pool_rows = session.scalars(select(Pool)).all()
            relay_rows = session.scalars(select(RelayKey)).all()
            key_rows = session.scalars(select(TavilyKey)).all()

        global_http_proxy = self._decrypt_optional(settings.http_proxy_encrypted)
        global_https_proxy = self._decrypt_optional(settings.https_proxy_encrypted)
        keys_by_pool: dict[str, dict[str, KeyRuntime]] = {}
        for key_row in key_rows:
            old_key = _find_previous_key(previous, key_row.id)
            quota = calculate_quota(
                key_usage=key_row.usage,
                key_limit=key_row.usage_limit,
                account_plan_usage=key_row.account_plan_usage,
                account_plan_limit=key_row.account_plan_limit,
                paygo_usage=key_row.paygo_usage,
                paygo_limit=key_row.paygo_limit,
            )
            keys_by_pool.setdefault(key_row.pool_id, {})[key_row.id] = KeyRuntime(
                id=key_row.id,
                pool_id=key_row.pool_id,
                name=key_row.name,
                api_key=self._secrets.decrypt(key_row.encrypted_key),
                enabled=key_row.enabled,
                status=key_row.status,
                usage=key_row.usage,
                usage_limit=key_row.usage_limit,
                account_plan=key_row.account_plan,
                account_plan_usage=key_row.account_plan_usage,
                account_plan_limit=key_row.account_plan_limit,
                paygo_usage=key_row.paygo_usage,
                paygo_limit=key_row.paygo_limit,
                synced_remaining=quota.effective_remaining,
                cooldown_until=key_row.cooldown_until,
                last_checked_at=key_row.last_checked_at,
                last_used_at=key_row.last_used_at,
                request_count=key_row.request_count,
                success_count=key_row.success_count,
                failure_count=key_row.failure_count,
                last_error=key_row.last_error,
                inflight=old_key.inflight if old_key else 0,
                inflight_credits=old_key.inflight_credits if old_key else 0,
                local_consumed=old_key.local_consumed if old_key else 0,
                rate_limit_cooldowns=(
                    old_key.rate_limit_cooldowns.copy()
                    if old_key
                    else _deserialize_cooldowns(key_row.rate_limit_cooldowns)
                ),
            )

        pools: dict[str, PoolRuntime] = {}
        for pool_row in pool_rows:
            old_pool = previous.pools.get(pool_row.id)
            pools[pool_row.id] = PoolRuntime(
                id=pool_row.id,
                name=pool_row.name,
                enabled=pool_row.enabled,
                strategy=pool_row.strategy,
                monitor_interval_seconds=(
                    pool_row.monitor_interval_seconds or settings.monitor_interval_seconds
                ),
                max_attempts=pool_row.max_attempts or settings.max_attempts,
                concurrency_limit=pool_row.concurrency_limit,
                rpm_limit=pool_row.rpm_limit,
                profile=ConnectionProfile(
                    base_url=pool_row.upstream_base_url or settings.upstream_base_url,
                    http_proxy=(
                        self._decrypt_optional(pool_row.http_proxy_encrypted)
                        if pool_row.http_proxy_encrypted is not None
                        else global_http_proxy
                    ),
                    https_proxy=(
                        self._decrypt_optional(pool_row.https_proxy_encrypted)
                        if pool_row.https_proxy_encrypted is not None
                        else global_https_proxy
                    ),
                    allow_direct_fallback=(
                        pool_row.allow_direct_fallback
                        if pool_row.allow_direct_fallback is not None
                        else settings.allow_direct_fallback
                    ),
                    timeout_seconds=settings.request_timeout_seconds,
                ),
                keys=keys_by_pool.get(pool_row.id, {}),
                active_requests=old_pool.active_requests if old_pool else 0,
                recent_requests=old_pool.recent_requests if old_pool else deque(),
            )

        relay_keys = {
            relay_row.id: RelayRuntime(
                id=relay_row.id,
                pool_id=relay_row.pool_id,
                secret_hash=relay_row.secret_hash,
                enabled=relay_row.enabled,
                last_used_at=relay_row.last_used_at,
            )
            for relay_row in relay_rows
        }
        return RuntimeSnapshot(
            pools=pools,
            relay_keys=relay_keys,
            generation=previous.generation + 1,
        )

    def load_affinities(self) -> dict[tuple[str, str], str]:
        with self._database.session() as session:
            rows = session.scalars(select(TaskAffinity)).all()
        return {(row.pool_id, row.resource_id): row.key_id for row in rows}

    def _decrypt_optional(self, value: str | None) -> str | None:
        return self._secrets.decrypt(value) if value else None


def _find_previous_key(snapshot: RuntimeSnapshot, key_id: str) -> KeyRuntime | None:
    for pool in snapshot.pools.values():
        if key_id in pool.keys:
            return pool.keys[key_id]
    return None


def _deserialize_cooldowns(value: dict[str, str] | None) -> dict[str, datetime]:
    if not value:
        return {}
    cooldowns: dict[str, datetime] = {}
    for bucket, serialized in value.items():
        try:
            cooldowns[bucket] = datetime.fromisoformat(serialized)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid persisted rate-limit cooldown")
    return cooldowns
