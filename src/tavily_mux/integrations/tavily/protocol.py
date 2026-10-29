import re

from tavily_mux.integrations.tavily.billing import json_object

_REQUEST_ID_PATTERN = re.compile(rb'"request_id"\s*:\s*"([A-Za-z0-9._:-]{1,200})"')


def json_request_id(body: bytes) -> str | None:
    value = json_object(body).get("request_id")
    return value if isinstance(value, str) and value else None


def streamed_request_id(body: bytes) -> str | None:
    direct = json_request_id(body)
    if direct is not None:
        return direct
    match = _REQUEST_ID_PATTERN.search(body)
    if match is not None:
        return match.group(1).decode()
    try:
        lines = body.decode().splitlines()
    except UnicodeDecodeError:
        return None
    for line in lines:
        if not line.startswith("data:"):
            continue
        request_id = json_request_id(line.removeprefix("data:").strip().encode())
        if request_id is not None:
            return request_id
    return None


def requests_stream(body: bytes) -> bool:
    return json_object(body).get("stream") is True
