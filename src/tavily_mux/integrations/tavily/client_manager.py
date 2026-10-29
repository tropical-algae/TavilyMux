import asyncio
from collections.abc import Sequence

import httpx2

from tavily_mux.runtime.models import ConnectionProfile


def is_unambiguous_transport_error(error: httpx2.HTTPError) -> bool:
    return isinstance(
        error,
        (
            httpx2.ConnectError,
            httpx2.ConnectTimeout,
            httpx2.PoolTimeout,
            httpx2.ProxyError,
        ),
    )


class TavilyClientManager:
    def __init__(
        self,
        *,
        max_connections: int,
        max_keepalive_connections: int,
    ) -> None:
        self._clients: dict[tuple[ConnectionProfile, bool], httpx2.AsyncClient] = {}
        self._lock = asyncio.Lock()
        self._limits = httpx2.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=30,
        )

    async def send(
        self,
        profile: ConnectionProfile,
        *,
        method: str,
        path: str,
        headers: Sequence[tuple[str, str]],
        content: bytes | None = None,
        query: str = "",
        stream: bool = False,
        retry_ambiguous_transport: bool = True,
    ) -> httpx2.Response:
        url = f"{profile.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        client = await self._get_client(profile, direct=False)
        request = client.build_request(method, url, headers=headers, content=content)
        try:
            return await client.send(request, stream=stream)
        except httpx2.TransportError as error:
            if not profile.allow_direct_fallback or not self._has_proxy(profile):
                raise
            if not retry_ambiguous_transport and not is_unambiguous_transport_error(error):
                raise
            direct_client = await self._get_client(profile, direct=True)
            direct_request = direct_client.build_request(
                method,
                url,
                headers=headers,
                content=content,
            )
            return await direct_client.send(direct_request, stream=stream)

    async def close(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        await asyncio.gather(*(client.aclose() for client in clients))

    async def _get_client(
        self,
        profile: ConnectionProfile,
        *,
        direct: bool,
    ) -> httpx2.AsyncClient:
        cache_key = (profile, direct)
        client = self._clients.get(cache_key)
        if client is not None:
            return client
        async with self._lock:
            client = self._clients.get(cache_key)
            if client is None:
                client = self._build_client(profile, direct=direct)
                self._clients[cache_key] = client
            return client

    def _build_client(
        self,
        profile: ConnectionProfile,
        *,
        direct: bool,
    ) -> httpx2.AsyncClient:
        mounts: dict[str, httpx2.AsyncBaseTransport | None] | None = None
        if not direct:
            configured_mounts: dict[str, httpx2.AsyncBaseTransport | None] = {}
            if profile.http_proxy:
                configured_mounts["http://"] = httpx2.AsyncHTTPTransport(
                    proxy=profile.http_proxy,
                    limits=self._limits,
                    http2=True,
                )
            if profile.https_proxy:
                configured_mounts["https://"] = httpx2.AsyncHTTPTransport(
                    proxy=profile.https_proxy,
                    limits=self._limits,
                    http2=True,
                )
            mounts = configured_mounts or None
        return httpx2.AsyncClient(
            http2=True,
            mounts=mounts,
            timeout=httpx2.Timeout(profile.timeout_seconds),
            limits=self._limits,
            trust_env=False,
        )

    @staticmethod
    def _has_proxy(profile: ConnectionProfile) -> bool:
        return bool(profile.http_proxy or profile.https_proxy)
