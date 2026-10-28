import json
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any

import httpx2
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI

from tavily_mux.app import create_app
from tavily_mux.common.config import Settings
from tavily_mux.services.bootstrap import ApplicationContext


@pytest.fixture
async def app_client(
    tmp_path: Path,
) -> AsyncIterator[tuple[FastAPI, httpx2.AsyncClient]]:
    settings = Settings(
        DATA_DIR=tmp_path,
        ADMIN_SECRET="test-admin-secret",
        MASTER_KEY=Fernet.generate_key().decode(),
        MAX_REQUEST_BODY_BYTES=1024,
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        yield app, client


async def provision_pool(
    client: httpx2.AsyncClient,
    *,
    keys: int = 1,
) -> tuple[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"secret": "test-admin-secret"},
    )
    csrf = login.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    pool_response = await client.post(
        "/api/v1/pools",
        headers=headers,
        json={"name": "proxy-pool", "max_attempts": 5},
    )
    pool = pool_response.json()
    pool_id = pool["id"]
    for index in range(keys):
        response = await client.post(
            f"/api/v1/pools/{pool_id}/keys",
            headers=headers,
            json={
                "name": f"key-{index}",
                "api_key": f"fake-upstream-key-{index}-long-enough",
            },
        )
        assert response.status_code == 201
    return pool_id, str(pool["relay_key"])


def response(status_code: int, body: bytes, **headers: str) -> httpx2.Response:
    return httpx2.Response(
        status_code,
        stream=httpx2.ByteStream(body),
        headers=headers,
        request=httpx2.Request("POST", "https://upstream.test/search"),
    )


Send = Callable[..., Coroutine[Any, Any, httpx2.Response]]


def replace_send(
    monkeypatch: pytest.MonkeyPatch,
    context: ApplicationContext,
    fake: Send,
) -> None:
    monkeypatch.setattr(context.clients, "send", fake)


async def test_search_is_a_schema_free_transparent_proxy(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    pool_id, relay_key = await provision_pool(client)
    del pool_id
    calls: list[dict[str, Any]] = []

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        calls.append(kwargs)
        return response(
            200,
            b'{"future_field":{"nested":[1,null,true]},"results":[]}',
            **{"content-type": "application/json", "x-upstream": "preserved"},
        )

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    body = {
        "query": "schema-free",
        "future_option": {"nested": [1, None, True]},
    }
    result = await client.post(
        "/search?future_query=value",
        headers={
            "Authorization": f"Bearer {relay_key}",
            "X-Future-Tavily-Header": "keep-me",
        },
        json=body,
    )

    assert result.status_code == 200
    assert result.json()["future_field"]["nested"] == [1, None, True]
    assert result.headers["x-upstream"] == "preserved"
    assert result.headers["x-tavily-mux-request-id"]
    assert len(calls) == 1
    assert calls[0]["query"] == "future_query=value"
    assert httpx2.Headers(calls[0]["headers"])["authorization"].startswith(
        "Bearer fake-upstream-key-"
    )
    assert httpx2.Headers(calls[0]["headers"])["x-future-tavily-header"] == "keep-me"
    assert json.loads(calls[0]["content"]) == body

    await context.events.flush()
    logs = await client.get("/api/v1/logs")
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["status_code"] == 200
    assert logs.json()["items"][0]["attempt_count"] == 1


async def test_key_specific_error_fails_over_and_logs_attempts(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    pool_id, relay_key = await provision_pool(client, keys=2)
    upstream_responses = [
        response(432, b'{"detail":{"error":"exhausted"}}'),
        response(200, b'{"results":[{"title":"ok"}]}'),
    ]
    authorizations: list[str] = []

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        authorizations.append(httpx2.Headers(kwargs["headers"])["authorization"])
        return upstream_responses.pop(0)

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    result = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        json={"query": "fail over"},
    )

    assert result.status_code == 200
    assert result.json() == {"results": [{"title": "ok"}]}
    assert len(authorizations) == 2
    assert authorizations[0] != authorizations[1]
    assert any(
        key.status == "exhausted"
        for key in context.runtime.snapshot.pools[pool_id].keys.values()
    )

    await context.events.flush()
    logs = await client.get(f"/api/v1/logs?pool_id={pool_id}")
    log = logs.json()["items"][0]
    assert log["attempt_count"] == 2
    assert [attempt["status_code"] for attempt in log["attempts"]] == [432, 200]
    filtered = await client.get(
        "/api/v1/logs",
        params={
            "pool_id": pool_id,
            "key_id": log["attempts"][0]["key_id"],
            "success": True,
            "retried": True,
            "request_id": log["id"][:8],
        },
    )
    assert filtered.json()["total"] == 1
    assert (await client.get("/api/v1/logs?retried=false")).json()["total"] == 0

    pool = await client.get(f"/api/v1/pools/{pool_id}")
    assert pool.json()["requests_today"] == 1
    assert pool.json()["success_rate_today"] == 100
    assert pool.json()["last_used_at"] is not None


async def test_last_upstream_error_is_returned_without_rewriting(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    _, relay_key = await provision_pool(client, keys=2)
    upstream_responses = [
        response(432, b'{"detail":{"error":"first"}}'),
        response(
            433,
            b'{"detail":{"error":"last exact error"},"new":true}',
            **{"content-type": "application/json", "retry-after": "7"},
        ),
    ]

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        return upstream_responses.pop(0)

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    result = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        content=b'{"query":"unchanged"}',
    )

    assert result.status_code == 433
    assert result.content == b'{"detail":{"error":"last exact error"},"new":true}'
    assert result.headers["retry-after"] == "7"


async def test_rejects_invalid_relay_key_and_oversized_body(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
) -> None:
    _, client = app_client
    invalid = await client.post(
        "/search",
        headers={"Authorization": "Bearer not-a-relay-key"},
        json={"query": "no"},
    )
    assert invalid.status_code == 401
    assert invalid.headers["x-tavily-mux-error"] == "invalid_relay_key"

    _, relay_key = await provision_pool(client)
    oversized = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        content=b"x" * 1025,
    )
    assert oversized.status_code == 413


async def test_transport_failures_try_each_key_then_return_gateway_error(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    _, relay_key = await provision_pool(client, keys=2)
    calls = 0

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ConnectError(
            "unreachable",
            request=httpx2.Request("POST", "https://upstream.test/search"),
        )

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    result = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        json={"query": "network failure"},
    )

    assert result.status_code == 502
    assert result.headers["x-tavily-mux-error"] == "upstream_unavailable"
    assert calls == 2


async def test_manual_usage_check_updates_key_and_timeline(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    pool_id, _ = await provision_pool(client)
    key_listing = await client.get(f"/api/v1/pools/{pool_id}/keys")
    key_id = key_listing.json()[0]["id"]

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "key": {"usage": 91, "limit": 100},
                "account": {
                    "current_plan": "Test",
                    "plan_usage": 91,
                    "plan_limit": 100,
                    "paygo_usage": 0,
                    "paygo_limit": 10,
                },
            },
            request=httpx2.Request("GET", "https://upstream.test/usage"),
        )

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    checked = await client.post(
        f"/api/v1/pools/{pool_id}/keys/{key_id}/check",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )

    assert checked.status_code == 200
    assert checked.json()["status"] == "low_quota"
    assert checked.json()["usage"] == 91
    assert checked.json()["estimated_remaining"] == 9
    timeline = await client.get(f"/api/v1/pools/{pool_id}/keys/{key_id}/usage")
    assert len(timeline.json()) == 1
    assert timeline.json()[0]["account_plan_limit"] == 100


async def test_usage_check_uses_account_quota_for_an_unlimited_key(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    pool_id, relay_key = await provision_pool(client)
    key_listing = await client.get(f"/api/v1/pools/{pool_id}/keys")
    key_id = key_listing.json()[0]["id"]
    account_usage = 7

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        if kwargs["path"] == "/search":
            return response(200, b'{"results":[]}')
        return httpx2.Response(
            200,
            json={
                "key": {"usage": account_usage, "limit": None},
                "account": {
                    "current_plan": "Researcher",
                    "plan_usage": account_usage,
                    "plan_limit": 1000,
                    "paygo_usage": 0,
                    "paygo_limit": None,
                },
            },
            request=httpx2.Request("GET", "https://upstream.test/usage"),
        )

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    checked = await client.post(
        f"/api/v1/pools/{pool_id}/keys/{key_id}/check",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )

    assert checked.status_code == 200
    assert checked.json()["usage_limit"] is None
    assert checked.json()["key_remaining"] is None
    assert checked.json()["account_remaining"] == 993
    assert checked.json()["estimated_remaining"] == 993
    assert checked.json()["quota_bottleneck"] == "account"

    search_result = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        json={"query": "local estimate"},
    )
    assert search_result.status_code == 200
    refreshed = await client.get(f"/api/v1/pools/{pool_id}/keys")
    assert refreshed.json()[0]["estimated_remaining"] == 992

    delayed = await client.post(
        f"/api/v1/pools/{pool_id}/keys/{key_id}/check",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )
    assert delayed.json()["usage"] == 7
    assert delayed.json()["estimated_remaining"] == 992

    account_usage = 8
    confirmed = await client.post(
        f"/api/v1/pools/{pool_id}/keys/{key_id}/check",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )
    assert confirmed.json()["usage"] == 8
    assert confirmed.json()["estimated_remaining"] == 992

    account_usage = 1000
    exhausted = await client.post(
        f"/api/v1/pools/{pool_id}/keys/{key_id}/check",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )
    assert exhausted.json()["status"] == "exhausted"
    assert exhausted.json()["estimated_remaining"] == 0

    timeline = await client.get(f"/api/v1/pools/{pool_id}/keys/{key_id}/usage")
    assert [item["estimated_remaining"] for item in timeline.json()] == [993, 993, 992, 0]


async def test_pool_without_keys_returns_clear_service_error(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
) -> None:
    _, client = app_client
    _, relay_key = await provision_pool(client, keys=0)
    result = await client.post(
        "/search",
        headers={"Authorization": f"Bearer {relay_key}"},
        json={"query": "no key"},
    )
    assert result.status_code == 503
    assert result.headers["x-tavily-mux-error"] == "no_available_key"


async def test_control_plane_can_test_saved_connection(
    app_client: tuple[FastAPI, httpx2.AsyncClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    await provision_pool(client, keys=0)

    async def fake_send(*args: Any, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(
            404,
            request=httpx2.Request("GET", "https://upstream.test/"),
        )

    context: ApplicationContext = app.state.context
    replace_send(monkeypatch, context, fake_send)
    tested = await client.post(
        "/api/v1/settings/test",
        headers={"X-CSRF-Token": client.cookies["tavily_mux_csrf"]},
    )

    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert tested.json()["status_code"] == 404
