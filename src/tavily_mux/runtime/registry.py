import asyncio
import hmac
import random
import time
from collections import deque
from datetime import timedelta

from sqlalchemy import select

from tavily_mux.common.security import SecretManager, parse_relay_key
from tavily_mux.common.time import utc_now
from tavily_mux.domain.enums import KeyStatus, RoutingStrategy
from tavily_mux.domain.quota import calculate_quota
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import Pool, RelayKey, SystemSettings, TavilyKey
from tavily_mux.runtime.models import (
    ConnectionProfile,
    KeyRuntime,
    PoolRuntime,
    RelayRuntime,
    RuntimeSnapshot,
)

ROUTABLE_STATUSES = {
    KeyStatus.UNKNOWN.value,
    KeyStatus.AVAILABLE.value,
    KeyStatus.LOW_QUOTA.value,
    KeyStatus.CHECK_FAILED.value,
}


class RuntimeRegistry:
    def __init__(
        self,
        database: Database,
        secrets: SecretManager,
        *,
        global_max_concurrency: int,
    ) -> None:
        self.database = database
        self.secrets = secrets
        self._snapshot = RuntimeSnapshot(pools={}, relay_keys={}, generation=0)
        self.global_slots = asyncio.Semaphore(global_max_concurrency)

    @property
    def snapshot(self) -> RuntimeSnapshot:
        return self._snapshot

    def load(self) -> RuntimeSnapshot:
        previous = self._snapshot
        with self.database.session() as session:
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
            old_key = self._find_previous_key(previous, key_row.id)
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
                api_key=self.secrets.decrypt(key_row.encrypted_key),
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
                local_consumed=old_key.local_consumed if old_key else 0,
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
        self._snapshot = RuntimeSnapshot(
            pools=pools,
            relay_keys=relay_keys,
            generation=previous.generation + 1,
        )
        return self._snapshot

    def authenticate_relay(self, token: str) -> PoolRuntime | None:
        parsed = parse_relay_key(token)
        if parsed is None:
            return None
        key_id, secret = parsed
        relay = self._snapshot.relay_keys.get(key_id)
        if relay is None or not relay.enabled:
            return None
        expected = self.secrets.digest(secret, purpose="relay-key")
        if not hmac.compare_digest(relay.secret_hash, expected):
            return None
        relay.last_used_at = utc_now()
        pool = self._snapshot.pools.get(relay.pool_id)
        return pool if pool and pool.enabled else None

    async def select_key(self, pool: PoolRuntime, tried: set[str]) -> KeyRuntime | None:
        async with pool.lock:
            self._trim_rpm_window(pool)
            if (
                pool.concurrency_limit is not None
                and pool.active_requests >= pool.concurrency_limit
            ):
                return None
            if pool.rpm_limit is not None and len(pool.recent_requests) >= pool.rpm_limit:
                return None

            now = utc_now()
            candidates: list[tuple[KeyRuntime, int | None]] = []
            for key in pool.keys.values():
                if key.id in tried or not key.enabled:
                    continue
                if key.status == KeyStatus.RATE_LIMITED.value:
                    if key.cooldown_until is None or key.cooldown_until > now:
                        continue
                    key.status = KeyStatus.AVAILABLE.value
                    key.cooldown_until = None
                if key.status not in ROUTABLE_STATUSES:
                    continue
                remaining = key.remaining
                if remaining == 0:
                    continue
                candidates.append((key, remaining))

            if not candidates:
                return None
            if pool.strategy == RoutingStrategy.RANDOM.value:
                selected = random.choice(candidates)[0]
            else:
                known = [item for item in candidates if item[1] is not None]
                ranked = known or candidates
                best_score = max(
                    (
                        remaining if remaining is not None else -1,
                        -key.inflight,
                    )
                    for key, remaining in ranked
                )
                best = [
                    key
                    for key, remaining in ranked
                    if (
                        remaining if remaining is not None else -1,
                        -key.inflight,
                    )
                    == best_score
                ]
                selected = random.choice(best)

            selected.inflight += 1
            selected.request_count += 1
            selected.last_used_at = now
            pool.active_requests += 1
            pool.recent_requests.append(time.monotonic())
            return selected

    async def finish_key(
        self,
        pool: PoolRuntime,
        key: KeyRuntime,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        async with pool.lock:
            key.inflight = max(key.inflight - 1, 0)
            pool.active_requests = max(pool.active_requests - 1, 0)
            if success:
                key.local_consumed += 1
                key.success_count += 1
                key.last_error = None
            else:
                key.failure_count += 1
                key.last_error = error

    async def mark_key_response(
        self,
        pool: PoolRuntime,
        key: KeyRuntime,
        status_code: int,
        retry_after_seconds: int | None = None,
    ) -> None:
        async with pool.lock:
            if status_code == 401:
                key.status = KeyStatus.INVALID.value
            elif status_code == 429:
                key.status = KeyStatus.RATE_LIMITED.value
                key.cooldown_until = utc_now() + timedelta(
                    seconds=max(retry_after_seconds or 60, 1)
                )
            elif status_code in {432, 433}:
                key.status = KeyStatus.EXHAUSTED.value

    def _decrypt_optional(self, value: str | None) -> str | None:
        return self.secrets.decrypt(value) if value else None

    @staticmethod
    def _find_previous_key(snapshot: RuntimeSnapshot, key_id: str) -> KeyRuntime | None:
        for pool in snapshot.pools.values():
            if key_id in pool.keys:
                return pool.keys[key_id]
        return None

    @staticmethod
    def _trim_rpm_window(pool: PoolRuntime) -> None:
        boundary = time.monotonic() - 60
        while pool.recent_requests and pool.recent_requests[0] < boundary:
            pool.recent_requests.popleft()
