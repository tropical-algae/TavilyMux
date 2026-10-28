from collections.abc import Iterable

from starlette.datastructures import Headers

HOP_BY_HOP_HEADERS = {
    b"connection",
    b"keep-alive",
    b"proxy-authenticate",
    b"proxy-authorization",
    b"te",
    b"trailer",
    b"transfer-encoding",
    b"upgrade",
}

REQUEST_STRIP_HEADERS = HOP_BY_HOP_HEADERS | {
    b"authorization",
    b"content-length",
    b"cookie",
    b"host",
    b"x-csrf-token",
}


def upstream_request_headers(headers: Headers, api_key: str) -> list[tuple[str, str]]:
    forwarded = [
        (name.decode("latin-1"), value.decode("latin-1"))
        for name, value in headers.raw
        if name.lower() not in REQUEST_STRIP_HEADERS
    ]
    forwarded.append(("Authorization", f"Bearer {api_key}"))
    return forwarded


def downstream_response_headers(
    headers: Iterable[tuple[bytes, bytes]],
    request_id: str,
) -> list[tuple[bytes, bytes]]:
    forwarded = [
        (name, value) for name, value in headers if name.lower() not in HOP_BY_HOP_HEADERS
    ]
    forwarded.append((b"x-tavily-mux-request-id", request_id.encode("ascii")))
    return forwarded
