import time
import uuid
from collections.abc import AsyncIterator

import httpx2
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from tavily_mux.api.dependencies import get_context
from tavily_mux.common.time import utc_now
from tavily_mux.integrations.tavily.error_classifier import (
    RETRYABLE_KEY_STATUS_CODES,
    error_type_for_status,
    retry_after_seconds,
)
from tavily_mux.integrations.tavily.header_policy import (
    downstream_response_headers,
    upstream_request_headers,
)
from tavily_mux.runtime.models import KeyRuntime, PoolRuntime
from tavily_mux.services.bootstrap import ApplicationContext
from tavily_mux.workers.events import KeyStateEvent, ProxyAttemptEvent, ProxyRequestEvent

router = APIRouter()


@router.post(
    "/search",
    response_class=Response,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": {"type": "object"}}},
        }
    },
)
async def search(request: Request) -> Response:
    context = get_context(request)
    token = _bearer_token(request.headers.get("authorization"))
    if token is None:
        return _local_error(status.HTTP_401_UNAUTHORIZED, "invalid_relay_key")
    pool = context.runtime.authenticate_relay(token)
    if pool is None:
        return _local_error(status.HTTP_401_UNAUTHORIZED, "invalid_relay_key")
    relay_id = token.split("_", maxsplit=2)[1]

    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > context.settings.MAX_REQUEST_BODY_BYTES
    ):
        return _local_error(status.HTTP_413_CONTENT_TOO_LARGE, "request_too_large")
    body = await request.body()
    if len(body) > context.settings.MAX_REQUEST_BODY_BYTES:
        return _local_error(status.HTTP_413_CONTENT_TOO_LARGE, "request_too_large")

    global_slots = context.runtime.global_slots
    if global_slots.locked():
        return _local_error(status.HTTP_503_SERVICE_UNAVAILABLE, "server_busy")
    await global_slots.acquire()
    try:
        return await _forward_search(
            request,
            context,
            pool,
            relay_id=relay_id,
            body=body,
        )
    except Exception:
        global_slots.release()
        raise


async def _forward_search(
    request: Request,
    context: ApplicationContext,
    pool: PoolRuntime,
    *,
    relay_id: str,
    body: bytes,
) -> Response:
    request_id = str(uuid.uuid4())
    external_request_id = request.headers.get("x-request-id")
    started_at = utc_now()
    started = time.perf_counter()
    attempts: list[ProxyAttemptEvent] = []
    tried: set[str] = set()
    touched: dict[str, KeyRuntime] = {}
    last_upstream: tuple[int, list[tuple[bytes, bytes]], bytes, str, str | None] | None = None

    while len(attempts) < pool.max_attempts:
        key = await context.runtime.select_key(pool, tried)
        if key is None:
            break
        tried.add(key.id)
        touched[key.id] = key
        attempt_no = len(attempts) + 1
        attempt_started = time.perf_counter()
        try:
            upstream = await context.clients.send(
                pool.profile,
                method="POST",
                path="/search",
                query=request.url.query,
                headers=upstream_request_headers(request.headers, key.api_key),
                content=body,
                stream=True,
            )
        except httpx2.HTTPError as error:
            latency_ms = (time.perf_counter() - attempt_started) * 1000
            error_type = type(error).__name__
            await context.runtime.finish_key(
                pool,
                key,
                success=False,
                error=error_type,
            )
            attempts.append(
                ProxyAttemptEvent(
                    attempt_no=attempt_no,
                    key_id=key.id,
                    status_code=None,
                    latency_ms=latency_ms,
                    error_type=error_type,
                )
            )
            continue

        latency_ms = (time.perf_counter() - attempt_started) * 1000
        response_error = error_type_for_status(upstream.status_code)
        if upstream.status_code in RETRYABLE_KEY_STATUS_CODES:
            raw_body = b"".join([chunk async for chunk in upstream.aiter_raw()])
            response_headers = list(upstream.headers.raw)
            await upstream.aclose()
            await context.runtime.mark_key_response(
                pool,
                key,
                upstream.status_code,
                retry_after_seconds(upstream.headers.get("retry-after")),
            )
            await context.runtime.finish_key(
                pool,
                key,
                success=False,
                error=response_error,
            )
            attempts.append(
                ProxyAttemptEvent(
                    attempt_no=attempt_no,
                    key_id=key.id,
                    status_code=upstream.status_code,
                    latency_ms=latency_ms,
                    error_type=response_error,
                )
            )
            last_upstream = (
                upstream.status_code,
                response_headers,
                raw_body,
                key.id,
                response_error,
            )
            continue

        attempts.append(
            ProxyAttemptEvent(
                attempt_no=attempt_no,
                key_id=key.id,
                status_code=upstream.status_code,
                latency_ms=latency_ms,
                error_type=response_error,
            )
        )
        return _stream_upstream(
            context,
            pool,
            key,
            upstream,
            request_id=request_id,
            relay_id=relay_id,
            external_request_id=external_request_id,
            started_at=started_at,
            started=started,
            attempts=attempts,
            touched=touched,
        )

    context.runtime.global_slots.release()
    if last_upstream is not None:
        status_code, headers, raw_body, final_key_id, final_error_type = last_upstream
        _emit_event(
            context,
            pool,
            request_id=request_id,
            relay_id=relay_id,
            external_request_id=external_request_id,
            started_at=started_at,
            started=started,
            status_code=status_code,
            final_key_id=final_key_id,
            error_type=final_error_type,
            attempts=attempts,
            touched=touched,
        )
        return _buffered_upstream(
            raw_body,
            status_code,
            headers,
            request_id=request_id,
        )

    error_type = "upstream_unavailable" if attempts else "no_available_key"
    status_code = (
        status.HTTP_502_BAD_GATEWAY if attempts else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    _emit_event(
        context,
        pool,
        request_id=request_id,
        relay_id=relay_id,
        external_request_id=external_request_id,
        started_at=started_at,
        started=started,
        status_code=status_code,
        final_key_id=None,
        error_type=error_type,
        attempts=attempts,
        touched=touched,
    )
    return _local_error(status_code, error_type, request_id=request_id)


def _stream_upstream(
    context: ApplicationContext,
    pool: PoolRuntime,
    key: KeyRuntime,
    upstream: httpx2.Response,
    *,
    request_id: str,
    relay_id: str,
    external_request_id: str | None,
    started_at,
    started: float,
    attempts: list[ProxyAttemptEvent],
    touched: dict[str, KeyRuntime],
) -> StreamingResponse:
    success = 200 <= upstream.status_code < 300

    async def body_iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await context.runtime.finish_key(
                pool,
                key,
                success=success,
                error=None if success else f"http_{upstream.status_code}",
            )
            context.runtime.global_slots.release()
            _emit_event(
                context,
                pool,
                request_id=request_id,
                relay_id=relay_id,
                external_request_id=external_request_id,
                started_at=started_at,
                started=started,
                status_code=upstream.status_code,
                final_key_id=key.id,
                error_type=None if success else f"http_{upstream.status_code}",
                attempts=attempts,
                touched=touched,
            )

    response = StreamingResponse(body_iterator(), status_code=upstream.status_code)
    response.raw_headers = downstream_response_headers(upstream.headers.raw, request_id)
    return response


def _buffered_upstream(
    body: bytes,
    status_code: int,
    headers: list[tuple[bytes, bytes]],
    *,
    request_id: str,
) -> Response:
    response = Response(content=body, status_code=status_code)
    response.raw_headers = downstream_response_headers(headers, request_id)
    return response


def _emit_event(
    context: ApplicationContext,
    pool: PoolRuntime,
    *,
    request_id: str,
    relay_id: str,
    external_request_id: str | None,
    started_at,
    started: float,
    status_code: int,
    final_key_id: str | None,
    error_type: str | None,
    attempts: list[ProxyAttemptEvent],
    touched: dict[str, KeyRuntime],
) -> None:
    completed_at = utc_now()
    context.events.emit(
        ProxyRequestEvent(
            request_id=request_id,
            pool_id=pool.id,
            relay_id=relay_id,
            created_at=started_at,
            completed_at=completed_at,
            status_code=status_code,
            latency_ms=(time.perf_counter() - started) * 1000,
            final_key_id=final_key_id,
            error_type=error_type,
            external_request_id=external_request_id,
            attempts=tuple(attempts),
            key_states=tuple(
                KeyStateEvent(
                    key_id=key.id,
                    status=key.status,
                    last_used_at=key.last_used_at,
                    cooldown_until=key.cooldown_until,
                    request_count=key.request_count,
                    success_count=key.success_count,
                    failure_count=key.failure_count,
                    last_error=key.last_error,
                )
                for key in touched.values()
            ),
        )
    )


def _local_error(
    status_code: int, error_type: str, *, request_id: str | None = None
) -> Response:
    headers = {"X-Tavily-Mux-Error": error_type}
    if request_id:
        headers["X-Tavily-Mux-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"error": error_type}},
        headers=headers,
    )


def _bearer_token(value: str | None) -> str | None:
    if value is None:
        return None
    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
