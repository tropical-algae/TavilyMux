from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from tavily_mux.common.security import SecretManager, generate_relay_key
from tavily_mux.common.time import utc_now
from tavily_mux.domain.endpoints import RateLimitBucket
from tavily_mux.domain.enums import KeyStatus, RoutingStrategy
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.migrate import upgrade_database
from tavily_mux.persistence.models import Pool, RelayKey, SystemSettings, TavilyKey
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.runtime.snapshot_loader import RuntimeSnapshotLoader


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[tuple[RuntimeRegistry, str]]:
    database_url = f"sqlite:///{tmp_path / 'runtime.db'}"
    database = Database(database_url)
    upgrade_database(database.engine)
    secret_manager = SecretManager(Fernet.generate_key())
    relay_id, relay_secret, relay_token = generate_relay_key()
    with database.session() as session:
        session.add(SystemSettings(id=1))
        session.add(
            Pool(
                id="pool-one",
                name="Primary",
                strategy=RoutingStrategy.MAX_REMAINING.value,
            )
        )
        session.add(
            RelayKey(
                id=relay_id,
                pool_id="pool-one",
                name="default",
                secret_hash=secret_manager.digest(relay_secret, purpose="relay-key"),
            )
        )
        session.add_all(
            [
                TavilyKey(
                    id="key-low",
                    pool_id="pool-one",
                    name="Low",
                    encrypted_key=secret_manager.encrypt("tvly-low"),
                    fingerprint=secret_manager.digest("tvly-low", purpose="tavily-key"),
                    status=KeyStatus.AVAILABLE.value,
                    usage=90,
                    usage_limit=100,
                ),
                TavilyKey(
                    id="key-high",
                    pool_id="pool-one",
                    name="High",
                    encrypted_key=secret_manager.encrypt("tvly-high"),
                    fingerprint=secret_manager.digest("tvly-high", purpose="tavily-key"),
                    status=KeyStatus.AVAILABLE.value,
                    usage=10,
                    usage_limit=100,
                ),
            ]
        )
        session.commit()

    registry = RuntimeRegistry(
        RuntimeSnapshotLoader(database, secret_manager),
        secret_manager,
        global_max_concurrency=10,
    )
    registry.load()
    yield registry, relay_token
    database.close()


def test_runtime_loads_and_authenticates_relay(
    runtime: tuple[RuntimeRegistry, str],
) -> None:
    registry, relay_token = runtime

    pool = registry.authenticate_relay(relay_token)

    assert pool is not None
    assert pool.id == "pool-one"
    assert registry.authenticate_relay("invalid") is None
    assert registry.authenticate_relay(relay_token + "bad") is None
    assert registry.snapshot.generation == 1


async def test_max_remaining_routing_and_completion(
    runtime: tuple[RuntimeRegistry, str],
) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None
    assert pool.keys["key-high"].remaining == 90

    selected = await registry.select_key(pool, set())
    assert selected is not None
    assert selected.id == "key-high"
    assert selected.inflight == 1
    assert selected.remaining == 89
    assert pool.active_requests == 1

    await registry.finish_key(pool, selected, success=True)
    assert selected.inflight == 0
    assert selected.local_consumed == 1
    assert selected.remaining == 89
    assert selected.success_count == 1
    assert pool.active_requests == 0


async def test_max_remaining_uses_account_quota_for_unlimited_keys(
    runtime: tuple[RuntimeRegistry, str],
) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None
    low = pool.keys["key-low"]
    high = pool.keys["key-high"]

    low.usage_limit = None
    low.account_plan_usage = 990
    low.account_plan_limit = 1000
    low.paygo_usage = 0
    low.paygo_limit = None
    low.synced_remaining = 10
    high.usage_limit = None
    high.account_plan_usage = 100
    high.account_plan_limit = 1000
    high.paygo_usage = 0
    high.paygo_limit = None
    high.synced_remaining = 900

    selected = await registry.select_key(pool, set())

    assert selected is high
    await registry.finish_key(pool, selected, success=False)


async def test_router_excludes_a_key_with_zero_effective_quota(
    runtime: tuple[RuntimeRegistry, str],
) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None
    exhausted = pool.keys["key-high"]
    exhausted.account_plan_usage = 1000
    exhausted.account_plan_limit = 1000
    exhausted.synced_remaining = 0

    selected = await registry.select_key(pool, set())

    assert selected is pool.keys["key-low"]
    await registry.finish_key(pool, selected, success=False)


async def test_key_error_states_and_cooldown(runtime: tuple[RuntimeRegistry, str]) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None
    key = pool.keys["key-high"]

    await registry.mark_key_response(pool, key, 429, retry_after_seconds=5)
    assert key.status == KeyStatus.RATE_LIMITED.value
    assert key.cooldown_until is not None
    assert await registry.select_key(pool, {"key-low"}) is None

    key.cooldown_until = utc_now() - timedelta(seconds=1)
    selected = await registry.select_key(pool, {"key-low"})
    assert selected is key
    await registry.finish_key(pool, key, success=False, error="upstream error")
    assert key.failure_count == 1
    assert key.last_error == "upstream error"

    await registry.mark_key_response(pool, key, 401)
    assert key.status == KeyStatus.INVALID.value
    await registry.mark_key_response(pool, key, 433)
    assert key.status == KeyStatus.EXHAUSTED.value


async def test_rate_limit_cooldowns_are_isolated_by_endpoint_bucket(
    runtime: tuple[RuntimeRegistry, str],
) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None
    key = pool.keys["key-high"]

    await registry.mark_key_response(
        pool,
        key,
        429,
        rate_limit_bucket=RateLimitBucket.RESEARCH,
        retry_after_seconds=60,
    )

    default_request = await registry.select_key(
        pool,
        {"key-low"},
        rate_limit_bucket=RateLimitBucket.DEFAULT,
    )
    assert default_request is key
    await registry.finish_key(pool, key, success=False)
    assert (
        await registry.select_key(
            pool,
            {"key-low"},
            rate_limit_bucket=RateLimitBucket.RESEARCH,
        )
        is None
    )


async def test_pool_limits_and_random_strategy(
    runtime: tuple[RuntimeRegistry, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    registry, relay_token = runtime
    pool = registry.authenticate_relay(relay_token)
    assert pool is not None

    pool.concurrency_limit = 1
    pool.active_requests = 1
    assert await registry.select_key(pool, set()) is None

    pool.active_requests = 0
    pool.rpm_limit = 1
    pool.recent_requests.append(10**12)
    assert await registry.select_key(pool, set()) is None

    pool.rpm_limit = None
    pool.strategy = RoutingStrategy.RANDOM.value
    monkeypatch.setattr("random.choice", lambda values: values[0])
    selected = await registry.select_key(pool, set())
    assert selected is not None
