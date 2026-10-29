import asyncio
import time
from contextlib import suppress
from typing import Any

import httpx2
from loguru import logger

from tavily_mux.common.time import utc_now
from tavily_mux.domain.enums import KeyStatus
from tavily_mux.domain.quota import calculate_quota, status_for_quota
from tavily_mux.integrations.tavily.client_manager import TavilyClientManager
from tavily_mux.integrations.tavily.error_classifier import key_status_for_http_error
from tavily_mux.runtime.models import KeyRuntime, PoolRuntime
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.workers.event_writer import EventWriter
from tavily_mux.workers.events import UsageSnapshotEvent


class UsageMonitor:
    def __init__(
        self,
        runtime: RuntimeRegistry,
        clients: TavilyClientManager,
        events: EventWriter,
        *,
        concurrency: int,
    ) -> None:
        self._runtime = runtime
        self._clients = clients
        self._events = events
        self._semaphore = asyncio.Semaphore(concurrency)
        self._next_check: dict[str, float] = {}
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="usage-monitor")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        await task
        self._task = None

    async def check_key(self, pool: PoolRuntime, key: KeyRuntime) -> None:
        async with self._semaphore:
            await self._check_key(pool, key)

    async def _run(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            checks: list[asyncio.Task[None]] = []
            snapshot = self._runtime.snapshot
            existing_ids: set[str] = set()
            for pool in snapshot.pools.values():
                for key in pool.keys.values():
                    existing_ids.add(key.id)
                    if not key.enabled or now < self._next_check.get(key.id, 0):
                        continue
                    self._next_check[key.id] = now + pool.monitor_interval_seconds
                    checks.append(asyncio.create_task(self.check_key(pool, key)))
            if checks:
                await asyncio.gather(*checks, return_exceptions=True)
            self._next_check = {
                key_id: due
                for key_id, due in self._next_check.items()
                if key_id in existing_ids
            }
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=5)

    async def _check_key(self, pool: PoolRuntime, key: KeyRuntime) -> None:
        checked_at = utc_now()
        async with pool.lock:
            consumed_before_check = key.local_consumed
        try:
            response = await self._clients.send(
                pool.profile,
                method="GET",
                path="/usage",
                headers=(("Authorization", f"Bearer {key.api_key}"),),
            )
            status_code = response.status_code
            if status_code == 200:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Usage response is not an object")
                await self._apply_success(
                    pool,
                    key,
                    payload,
                    checked_at,
                    consumed_before_check,
                )
                return
            await self._apply_failure(pool, key, status_code, checked_at)
        except (httpx2.HTTPError, ValueError, TypeError) as error:
            logger.warning("Usage check failed for key {}: {}", key.id, type(error).__name__)
            await self._persist_result(
                pool,
                key,
                checked_at=checked_at,
                status=KeyStatus.CHECK_FAILED,
                error=type(error).__name__,
            )

    async def _apply_success(
        self,
        pool: PoolRuntime,
        key: KeyRuntime,
        payload: dict[str, Any],
        checked_at,
        consumed_before_check: int,
    ) -> None:
        key_data = _optional_dict(payload.get("key"))
        account = _optional_dict(payload.get("account"))
        usage = _optional_int(key_data.get("usage"))
        usage_limit = _optional_int(key_data.get("limit"))
        account_plan = _optional_str(account.get("current_plan"))
        account_plan_usage = _optional_int(account.get("plan_usage"))
        account_plan_limit = _optional_int(account.get("plan_limit"))
        paygo_usage = _optional_int(account.get("paygo_usage"))
        paygo_limit = _optional_int(account.get("paygo_limit"))
        status = status_for_quota(
            calculate_quota(
                key_usage=usage,
                key_limit=usage_limit,
                account_plan_usage=account_plan_usage,
                account_plan_limit=account_plan_limit,
                paygo_usage=paygo_usage,
                paygo_limit=paygo_limit,
            )
        )
        await self._persist_result(
            pool,
            key,
            checked_at=checked_at,
            status=status,
            usage=usage,
            usage_limit=usage_limit,
            account_plan=account_plan,
            account_plan_usage=account_plan_usage,
            account_plan_limit=account_plan_limit,
            paygo_usage=paygo_usage,
            paygo_limit=paygo_limit,
            consumed_before_check=consumed_before_check,
        )

    async def _apply_failure(
        self,
        pool: PoolRuntime,
        key: KeyRuntime,
        status_code: int,
        checked_at,
    ) -> None:
        status = key_status_for_http_error(status_code) or KeyStatus.CHECK_FAILED
        await self._persist_result(
            pool,
            key,
            checked_at=checked_at,
            status=status,
            error=f"usage_http_{status_code}",
        )

    async def _persist_result(
        self,
        pool: PoolRuntime,
        key: KeyRuntime,
        *,
        checked_at,
        status: KeyStatus,
        usage: int | None = None,
        usage_limit: int | None = None,
        account_plan: str | None = None,
        account_plan_usage: int | None = None,
        account_plan_limit: int | None = None,
        paygo_usage: int | None = None,
        paygo_limit: int | None = None,
        error: str | None = None,
        consumed_before_check: int | None = None,
    ) -> None:
        current_pool = self._runtime.snapshot.pools.get(pool.id)
        if current_pool is None or current_pool.keys.get(key.id) is not key:
            return
        async with pool.lock:
            key.status = status.value
            key.last_checked_at = checked_at
            key.last_error = error
            if status in {KeyStatus.AVAILABLE, KeyStatus.LOW_QUOTA, KeyStatus.EXHAUSTED}:
                confirmed_local_consumption = _confirmed_local_consumption(
                    previous_usage=key.usage,
                    current_usage=usage,
                    local_consumed_before_check=consumed_before_check,
                )
                key.usage = usage
                key.usage_limit = usage_limit
                key.account_plan = account_plan
                key.account_plan_usage = account_plan_usage
                key.account_plan_limit = account_plan_limit
                key.paygo_usage = paygo_usage
                key.paygo_limit = paygo_limit
                key.synced_remaining = calculate_quota(
                    key_usage=usage,
                    key_limit=usage_limit,
                    account_plan_usage=account_plan_usage,
                    account_plan_limit=account_plan_limit,
                    paygo_usage=paygo_usage,
                    paygo_limit=paygo_limit,
                ).effective_remaining
                key.local_consumed = max(
                    key.local_consumed - confirmed_local_consumption,
                    0,
                )
        self._events.emit_usage(
            UsageSnapshotEvent(
                key_id=key.id,
                checked_at=checked_at,
                status=status.value,
                usage=usage,
                usage_limit=usage_limit,
                account_plan=account_plan,
                account_plan_usage=account_plan_usage,
                account_plan_limit=account_plan_limit,
                paygo_usage=paygo_usage,
                paygo_limit=paygo_limit,
                error=error,
            )
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _confirmed_local_consumption(
    *,
    previous_usage: int | None,
    current_usage: int | None,
    local_consumed_before_check: int | None,
) -> int:
    if (
        local_consumed_before_check is None
        or local_consumed_before_check <= 0
        or previous_usage is None
        or current_usage is None
    ):
        return 0
    if current_usage < previous_usage:
        # A lower cumulative counter indicates a new billing cycle. The new
        # official snapshot supersedes all local estimates from the old cycle.
        return local_consumed_before_check
    return min(current_usage - previous_usage, local_consumed_before_check)
