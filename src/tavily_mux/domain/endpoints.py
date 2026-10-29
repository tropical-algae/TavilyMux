import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class EndpointMode(StrEnum):
    STATELESS = "stateless"
    TASK_CREATE = "task_create"
    TASK_READ = "task_read"
    FEEDBACK = "feedback"


class CreditProfile(StrEnum):
    SEARCH = "search"
    EXTRACT = "extract"
    CRAWL = "crawl"
    MAP = "map"
    RESEARCH = "research"
    NONE = "none"
    UNKNOWN = "unknown"


class RateLimitBucket(StrEnum):
    DEFAULT = "default"
    CRAWL = "crawl"
    RESEARCH = "research"


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    id: str
    method: Literal["GET", "POST"]
    path: str
    mode: EndpointMode
    credit_profile: CreditProfile
    rate_limit_bucket: RateLimitBucket


BUILTIN_ENDPOINTS = (
    EndpointSpec(
        "search",
        "POST",
        "/search",
        EndpointMode.STATELESS,
        CreditProfile.SEARCH,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        "extract",
        "POST",
        "/extract",
        EndpointMode.STATELESS,
        CreditProfile.EXTRACT,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        "crawl",
        "POST",
        "/crawl",
        EndpointMode.STATELESS,
        CreditProfile.CRAWL,
        RateLimitBucket.CRAWL,
    ),
    EndpointSpec(
        "map",
        "POST",
        "/map",
        EndpointMode.STATELESS,
        CreditProfile.MAP,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        "research",
        "POST",
        "/research",
        EndpointMode.TASK_CREATE,
        CreditProfile.RESEARCH,
        RateLimitBucket.RESEARCH,
    ),
    EndpointSpec(
        "research",
        "GET",
        "/research/{request_id}",
        EndpointMode.TASK_READ,
        CreditProfile.NONE,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        "feedback",
        "POST",
        "/feedback",
        EndpointMode.FEEDBACK,
        CreditProfile.NONE,
        RateLimitBucket.DEFAULT,
    ),
)

BUILTIN_ENDPOINT_IDS = frozenset(spec.id for spec in BUILTIN_ENDPOINTS)

_RESERVED_EXACT_PATHS = frozenset(
    {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/livez",
        "/readyz",
        "/login",
        "/pools",
        "/logs",
        "/settings",
        "/api",
        "/assets",
        "/usage",
        "/org-usage",
    }
)
_RESERVED_PREFIXES = (
    "/api/",
    "/assets/",
    "/docs/",
    "/redoc/",
    "/login/",
    "/pools/",
    "/logs/",
    "/settings/",
)
_INVALID_PERCENT_ENCODING = re.compile(r"%(?:2e|2f|5c)", re.IGNORECASE)
_REQUEST_ID_PATTERN = re.compile(rb'"request_id"\s*:\s*"([A-Za-z0-9._:-]{1,200})"')


def _uppercase_method(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


HttpMethod = Annotated[Literal["GET", "POST"], BeforeValidator(_uppercase_method)]


class CustomEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    method: HttpMethod = "POST"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = value.strip()
        if not path.startswith("/"):
            raise ValueError("endpoint path must start with '/'")
        if len(path) > 500:
            raise ValueError("endpoint path must not exceed 500 characters")
        if "?" in path or "#" in path:
            raise ValueError("endpoint path must not include a query or fragment")
        if "//" in path:
            raise ValueError("endpoint path must not contain repeated slashes")
        if any(part in {".", ".."} for part in path.split("/")):
            raise ValueError("endpoint path must not contain dot segments")
        if _INVALID_PERCENT_ENCODING.search(path):
            raise ValueError(
                "endpoint path must not contain encoded separators or dot segments"
            )
        if any(character in path for character in "{}*"):
            raise ValueError("custom endpoints do not support path parameters or wildcards")
        return path.rstrip("/") or "/"


class EndpointSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disabled: set[str] = Field(default_factory=set)
    custom: list[CustomEndpoint] = Field(default_factory=list)

    @field_validator("disabled")
    @classmethod
    def validate_disabled(cls, value: set[str]) -> set[str]:
        normalized = {item.strip().lower() for item in value}
        unknown = normalized - BUILTIN_ENDPOINT_IDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown built-in endpoint(s): {names}")
        return normalized

    @model_validator(mode="after")
    def validate_custom_routes(self) -> "EndpointSettings":
        seen: set[str] = set()
        for endpoint in self.custom:
            path = endpoint.path
            if path in seen:
                raise ValueError(f"custom endpoint path conflicts with another route: {path}")
            seen.add(path)
            if is_builtin_path(path):
                raise ValueError(
                    f"custom endpoint path conflicts with a built-in route: {path}"
                )
            if is_reserved_path(path):
                raise ValueError(f"custom endpoint path is reserved by TavilyMux: {path}")
        return self


def is_builtin_path(path: str) -> bool:
    for spec in BUILTIN_ENDPOINTS:
        if "{" not in spec.path and path == spec.path:
            return True
        if spec.path == "/research/{request_id}" and re.fullmatch(r"/research/[^/]+", path):
            return True
    return False


def is_reserved_path(path: str) -> bool:
    if path in _RESERVED_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _RESERVED_PREFIXES)


def endpoint_specs(settings: EndpointSettings) -> tuple[EndpointSpec, ...]:
    builtins = tuple(spec for spec in BUILTIN_ENDPOINTS if spec.id not in settings.disabled)
    custom = tuple(
        EndpointSpec(
            id="custom",
            method=endpoint.method,
            path=endpoint.path,
            mode=EndpointMode.STATELESS,
            credit_profile=CreditProfile.UNKNOWN,
            rate_limit_bucket=RateLimitBucket.DEFAULT,
        )
        for endpoint in settings.custom
    )
    return (*builtins, *custom)


def estimate_credits(profile: CreditProfile, body: bytes) -> int:
    if profile is CreditProfile.NONE:
        return 0
    if profile is CreditProfile.UNKNOWN:
        return 1
    payload = _json_object(body)
    if profile is CreditProfile.SEARCH:
        return 2 if payload.get("search_depth") == "advanced" else 1
    if profile is CreditProfile.EXTRACT:
        return 2 if payload.get("extract_depth") == "advanced" else 1
    if profile is CreditProfile.MAP:
        return 2 if payload.get("instructions") else 1
    if profile is CreditProfile.CRAWL:
        extraction = 2 if payload.get("extract_depth") == "advanced" else 1
        mapping = 2 if payload.get("instructions") else 1
        return mapping + extraction
    if profile is CreditProfile.RESEARCH:
        return 15 if payload.get("model") == "pro" else 4
    return 1


def json_request_id(body: bytes) -> str | None:
    value = _json_object(body).get("request_id")
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
    return _json_object(body).get("stream") is True


def _json_object(body: bytes) -> dict[str, object]:
    if not body:
        return {}
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
