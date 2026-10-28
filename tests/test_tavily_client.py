from typing import Any

import httpx2
import pytest

from tavily_mux.integrations.tavily.client_manager import TavilyClientManager
from tavily_mux.runtime.models import ConnectionProfile


async def test_client_manager_reuses_client_and_builds_target_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json={"ok": True})

    manager = TavilyClientManager(max_connections=10, max_keepalive_connections=5)
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    builds = 0

    def build_client(*args: Any, **kwargs: Any) -> httpx2.AsyncClient:
        nonlocal builds
        builds += 1
        return client

    monkeypatch.setattr(manager, "_build_client", build_client)
    profile = ConnectionProfile(
        base_url="https://api.example.test/root/",
        http_proxy=None,
        https_proxy=None,
        allow_direct_fallback=False,
        timeout_seconds=10,
    )
    first = await manager.send(
        profile,
        method="POST",
        path="/search",
        query="mode=future",
        headers=(("Authorization", "Bearer secret"),),
        content=b"{}",
    )
    second = await manager.send(
        profile,
        method="GET",
        path="usage",
        headers=(),
    )

    assert first.status_code == second.status_code == 200
    assert builds == 1
    assert str(requests[0].url) == "https://api.example.test/root/search?mode=future"
    assert str(requests[1].url) == "https://api.example.test/root/usage"
    await manager.close()


async def test_client_manager_can_fallback_to_direct_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proxy_handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("proxy down", request=request)

    async def direct_handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text="direct")

    proxy_client = httpx2.AsyncClient(transport=httpx2.MockTransport(proxy_handler))
    direct_client = httpx2.AsyncClient(transport=httpx2.MockTransport(direct_handler))
    manager = TavilyClientManager(max_connections=10, max_keepalive_connections=5)

    def build_client(profile: ConnectionProfile, *, direct: bool) -> httpx2.AsyncClient:
        return direct_client if direct else proxy_client

    monkeypatch.setattr(manager, "_build_client", build_client)
    profile = ConnectionProfile(
        base_url="https://api.example.test",
        http_proxy="http://proxy.example.test:7890",
        https_proxy="http://proxy.example.test:7890",
        allow_direct_fallback=True,
        timeout_seconds=10,
    )
    result = await manager.send(
        profile,
        method="GET",
        path="usage",
        headers=(),
    )

    assert result.text == "direct"
    await manager.close()
