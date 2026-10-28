RETRYABLE_KEY_STATUS_CODES = frozenset({401, 429, 432, 433})


def error_type_for_status(status_code: int) -> str | None:
    return {
        401: "invalid_key",
        429: "rate_limited",
        432: "plan_limit_exceeded",
        433: "paygo_limit_exceeded",
    }.get(status_code)


def retry_after_seconds(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return max(int(value), 0)
    except ValueError:
        return None
