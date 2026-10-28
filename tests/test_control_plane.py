from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest
from cryptography.fernet import Fernet

from tavily_mux.app import create_app
from tavily_mux.common.config import Settings


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx2.AsyncClient]:
    settings = Settings(
        DATA_DIR=tmp_path,
        ADMIN_SECRET="test-admin-secret",
        MASTER_KEY=Fernet.generate_key().decode(),
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
        ) as test_client,
    ):
        yield test_client


async def login(client: httpx2.AsyncClient, secret: str = "test-admin-secret") -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"secret": secret, "remember": True},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


async def test_authentication_csrf_and_logout(client: httpx2.AsyncClient) -> None:
    unauthenticated = await client.get("/api/v1/dashboard")
    assert unauthenticated.status_code == 401

    invalid = await client.post("/api/v1/auth/login", json={"secret": "wrong"})
    assert invalid.status_code == 401

    csrf = await login(client)
    assert (await client.get("/api/v1/auth/me")).json() == {"authenticated": True}

    missing_csrf = await client.patch(
        "/api/v1/settings",
        json={"monitor_interval_seconds": 600},
    )
    assert missing_csrf.status_code == 403

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_settings_and_pool_lifecycle(client: httpx2.AsyncClient) -> None:
    csrf = await login(client)
    headers = {"X-CSRF-Token": csrf}

    settings = await client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.json()["upstream_base_url"] == "https://api.tavily.com"

    updated = await client.patch(
        "/api/v1/settings",
        headers=headers,
        json={
            "upstream_base_url": "https://search.example.test/",
            "http_proxy": "http://alice:secret@proxy.example.test:7890",
            "monitor_interval_seconds": 600,
            "max_attempts": 4,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["upstream_base_url"] == "https://search.example.test"
    assert updated.json()["http_proxy"] == "http://alice:••••@proxy.example.test:7890"

    created = await client.post(
        "/api/v1/pools",
        headers=headers,
        json={"name": "primary", "description": "main pool", "strategy": "random"},
    )
    assert created.status_code == 201
    pool = created.json()
    pool_id = pool["id"]
    assert pool["relay_key"].startswith("tpool_")
    assert pool["status"] == "unavailable"

    duplicate = await client.post(
        "/api/v1/pools",
        headers=headers,
        json={"name": "primary"},
    )
    assert duplicate.status_code == 409

    listing = await client.get("/api/v1/pools")
    assert listing.status_code == 200
    assert "relay_key" not in listing.json()[0]

    patched = await client.patch(
        f"/api/v1/pools/{pool_id}",
        headers=headers,
        json={"strategy": "max_remaining", "concurrency_limit": 50},
    )
    assert patched.status_code == 200
    assert patched.json()["concurrency_limit"] == 50

    dashboard = await client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["pool_count"] == 1

    removed = await client.delete(f"/api/v1/pools/{pool_id}", headers=headers)
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/pools/{pool_id}")).status_code == 404


async def test_key_and_relay_management(client: httpx2.AsyncClient) -> None:
    csrf = await login(client)
    headers = {"X-CSRF-Token": csrf}
    pool_response = await client.post(
        "/api/v1/pools",
        headers=headers,
        json={"name": "managed"},
    )
    pool_id = pool_response.json()["id"]

    relays = await client.get(f"/api/v1/pools/{pool_id}/relay-keys")
    assert len(relays.json()) == 1
    relay = await client.post(
        f"/api/v1/pools/{pool_id}/relay-keys",
        headers=headers,
        json={"name": "automation"},
    )
    assert relay.status_code == 201
    relay_id = relay.json()["id"]
    assert relay.json()["relay_key"].startswith("tpool_")
    disabled_relay = await client.patch(
        f"/api/v1/pools/{pool_id}/relay-keys/{relay_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled_relay.json()["enabled"] is False
    assert (
        await client.delete(f"/api/v1/pools/{pool_id}/relay-keys/{relay_id}", headers=headers)
    ).status_code == 204

    key_value = "fake-tavily-key-development-one"
    created_key = await client.post(
        f"/api/v1/pools/{pool_id}/keys",
        headers=headers,
        json={"name": "one", "api_key": key_value},
    )
    assert created_key.status_code == 201
    key = created_key.json()
    key_id = key["id"]
    assert key_value not in key["masked_key"]
    assert key["status"] == "unknown"

    duplicate = await client.post(
        f"/api/v1/pools/{pool_id}/keys",
        headers=headers,
        json={"name": "duplicate", "api_key": key_value},
    )
    assert duplicate.status_code == 409
    assert "managed" in duplicate.json()["detail"]

    bulk = await client.post(
        f"/api/v1/pools/{pool_id}/keys/bulk",
        headers=headers,
        json={
            "keys": [
                {"name": "two", "api_key": "fake-tavily-key-development-two"},
                {"name": "three", "api_key": "fake-tavily-key-development-three"},
            ]
        },
    )
    assert bulk.status_code == 201
    assert len(bulk.json()) == 2

    disabled = await client.patch(
        f"/api/v1/pools/{pool_id}/keys/{key_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert disabled.json()["status"] == "disabled"
    enabled = await client.patch(
        f"/api/v1/pools/{pool_id}/keys/{key_id}",
        headers=headers,
        json={"enabled": True, "name": "renamed"},
    )
    assert enabled.json()["status"] == "unknown"
    assert enabled.json()["name"] == "renamed"

    usage = await client.get(f"/api/v1/pools/{pool_id}/keys/{key_id}/usage")
    assert usage.json() == []
    logs = await client.get("/api/v1/logs?page=1&page_size=10")
    assert logs.json() == {"items": [], "total": 0, "page": 1, "page_size": 10}

    assert (
        await client.delete(f"/api/v1/pools/{pool_id}/keys/{key_id}", headers=headers)
    ).status_code == 204


async def test_changing_admin_secret_revokes_existing_session(
    client: httpx2.AsyncClient,
) -> None:
    csrf = await login(client)
    changed = await client.put(
        "/api/v1/auth/secret",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_secret": "test-admin-secret",
            "new_secret": "new-test-admin-secret",
        },
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    await login(client, "new-test-admin-secret")
