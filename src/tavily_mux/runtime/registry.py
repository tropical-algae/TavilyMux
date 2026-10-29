import asyncio
import hmac
import random
import time
from datetime import timedelta

from tavily_mux.common.security import SecretManager, parse_relay_key
from tavily_mux.common.time import utc_now
from tavily_mux.domain.endpoints import RateLimitBucket
from tavily_mux.domain.enums import KeyStatus, RoutingStrategy
from tavily_mux.integrations.tavily.error_classifier import key_status_for_http_error
from tavily_mux.runtime.affinity import AffinityRegistry, AffinitySink
from tavily_mux.runtime.models import KeyRuntime, PoolRuntime, RuntimeSnapshot
from tavily_mux.runtime.snapshot_loader import RuntimeSnapshotLoader

ROUTABLE_STATUSES = {
    KeyStatus.UNKNOWN.value,
    KeyStatus.AVAILABLE.value,
    KeyStatus.LOW_QUOTA.value,
    KeyStatus.CHECK_FAILED.value,
}


class RuntimeRegistry:
    def __init__(
        self,
        loader: RuntimeSnapshotLoader,
        secrets: SecretManager,
        *,
        global_max_concurrency: int,
        affinity_sink: AffinitySink | None = None,
    ) -> None:
        self._loader = loader
        self._secrets = secrets
        self._snapshot = RuntimeSnapshot(pools={}, relay_keys={}, generation=0)
        self._affinities = AffinityRegistry(
            persistent=loader.load_affinities(),
            sink=affinity_sink,
        )
        self.global_slots = asyncio.Semaphore(global_max_concurrency)

    @property
    def snapshot(self) -> RuntimeSnapshot:
        return self._snapshot

    def load(self) -> RuntimeSnapshot:
        self._snapshot = self._loader.load(self._snapshot)
        return self._snapshot

    def authenticate_relay(self, token: str) -> PoolRuntime | None:
        parsed = parse_relay_key(token)
        if parsed is None:
            return None
        key_id, secret = parsed
        relay = self._snapshot.relay_keys.get(key_id)
        if relay is None or not relay.enabled:
            return None
        expected = self._secrets.digest(secret, purpose="relay-key")
        if not hmac.compare_digest(relay.secret_hash, expected):
            return None
        relay.last_used_at = utc_now()
        pool = self._snapshot.pools.get(relay.pool_id)
        return pool if pool and pool.enabled else None

    async def select_key(
        self,
        pool: PoolRuntime,
        tried: set[str],
        *,
        estimated_credits: int = 1,
        rate_limit_bucket: RateLimitBucket = RateLimitBucket.DEFAULT,
        preferred_key_id: str | None = None,
    ) -> KeyRuntime | None:
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
                if (
                    key.id in tried
                    or not key.enabled
                    or (preferred_key_id is not None and key.id != preferred_key_id)
                ):
                    continue
                self._refresh_rate_limit_state(key, now)
                bucket_cooldown = key.rate_limit_cooldowns.get(rate_limit_bucket.value)
                if bucket_cooldown is not None and bucket_cooldown > now:
                    continue
                if key.status not in ROUTABLE_STATUSES:
                    if key.status != KeyStatus.RATE_LIMITED.value:
                        continue
                    if not key.rate_limit_cooldowns:
                        key.status = KeyStatus.AVAILABLE.value
                remaining = key.remaining
                if remaining is not None and remaining < estimated_credits:
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
            selected.inflight_credits += estimated_credits
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
        consumed_credits: int = 1,
        error: str | None = None,
    ) -> None:
        async with pool.lock:
            key.inflight = max(key.inflight - 1, 0)
            key.inflight_credits = max(key.inflight_credits - consumed_credits, 0)
            pool.active_requests = max(pool.active_requests - 1, 0)
            if success:
                key.local_consumed += consumed_credits
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
        rate_limit_bucket: RateLimitBucket = RateLimitBucket.DEFAULT,
        retry_after_seconds: int | None = None,
    ) -> None:
        async with pool.lock:
            classified_status = key_status_for_http_error(status_code)
            if classified_status is KeyStatus.INVALID:
                key.status = classified_status.value
            elif classified_status is KeyStatus.RATE_LIMITED:
                if rate_limit_bucket is RateLimitBucket.DEFAULT:
                    key.status = classified_status.value
                cooldown_until = utc_now() + timedelta(
                    seconds=max(retry_after_seconds or 60, 1)
                )
                key.rate_limit_cooldowns[rate_limit_bucket.value] = cooldown_until
                key.cooldown_until = max(key.rate_limit_cooldowns.values())
            elif classified_status is KeyStatus.EXHAUSTED:
                key.status = classified_status.value

    def affinity_key_id(self, pool_id: str, resource_id: str) -> str | None:
        return self._affinities.key_id(pool_id, resource_id)

    def remember_affinity(
        self,
        pool_id: str,
        resource_id: str,
        key_id: str,
        *,
        persist: bool = True,
    ) -> None:
        self._affinities.remember(
            pool_id,
            resource_id,
            key_id,
            persist=persist,
        )

    @staticmethod
    def _trim_rpm_window(pool: PoolRuntime) -> None:
        boundary = time.monotonic() - 60
        while pool.recent_requests and pool.recent_requests[0] < boundary:
            pool.recent_requests.popleft()

    @staticmethod
    def _refresh_rate_limit_state(key: KeyRuntime, now) -> None:
        if (
            key.status == KeyStatus.RATE_LIMITED.value
            and key.cooldown_until is not None
            and key.cooldown_until <= now
        ):
            key.rate_limit_cooldowns.clear()
        expired = [
            bucket
            for bucket, cooldown_until in key.rate_limit_cooldowns.items()
            if cooldown_until <= now
        ]
        for bucket in expired:
            del key.rate_limit_cooldowns[bucket]
        if key.rate_limit_cooldowns:
            key.cooldown_until = max(key.rate_limit_cooldowns.values())
        if (
            key.status == KeyStatus.RATE_LIMITED.value
            and RateLimitBucket.DEFAULT.value not in key.rate_limit_cooldowns
        ):
            key.status = KeyStatus.AVAILABLE.value
        if not key.rate_limit_cooldowns:
            key.cooldown_until = None
