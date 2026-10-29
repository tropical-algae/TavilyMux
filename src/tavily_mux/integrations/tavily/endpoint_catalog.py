import re

from tavily_mux.common.config.endpoint import EndpointSettings
from tavily_mux.domain.endpoints import (
    BuiltinEndpoint,
    CreditProfile,
    EndpointMode,
    EndpointSpec,
    RateLimitBucket,
)

BUILTIN_ENDPOINTS = (
    EndpointSpec(
        BuiltinEndpoint.SEARCH,
        "POST",
        "/search",
        EndpointMode.STATELESS,
        CreditProfile.SEARCH,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        BuiltinEndpoint.EXTRACT,
        "POST",
        "/extract",
        EndpointMode.STATELESS,
        CreditProfile.EXTRACT,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        BuiltinEndpoint.CRAWL,
        "POST",
        "/crawl",
        EndpointMode.STATELESS,
        CreditProfile.CRAWL,
        RateLimitBucket.CRAWL,
    ),
    EndpointSpec(
        BuiltinEndpoint.MAP,
        "POST",
        "/map",
        EndpointMode.STATELESS,
        CreditProfile.MAP,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        BuiltinEndpoint.RESEARCH,
        "POST",
        "/research",
        EndpointMode.TASK_CREATE,
        CreditProfile.RESEARCH,
        RateLimitBucket.RESEARCH,
    ),
    EndpointSpec(
        BuiltinEndpoint.RESEARCH,
        "GET",
        "/research/{request_id}",
        EndpointMode.TASK_READ,
        CreditProfile.NONE,
        RateLimitBucket.DEFAULT,
    ),
    EndpointSpec(
        BuiltinEndpoint.FEEDBACK,
        "POST",
        "/feedback",
        EndpointMode.FEEDBACK,
        CreditProfile.NONE,
        RateLimitBucket.DEFAULT,
    ),
)


def endpoint_specs(settings: EndpointSettings) -> tuple[EndpointSpec, ...]:
    _validate_custom_paths(settings)
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


def is_builtin_path(path: str) -> bool:
    return any(_matches_route(spec.path, path) for spec in BUILTIN_ENDPOINTS)


def _validate_custom_paths(settings: EndpointSettings) -> None:
    for endpoint in settings.custom:
        if is_builtin_path(endpoint.path):
            raise ValueError(
                f"custom endpoint path conflicts with a built-in route: {endpoint.path}"
            )


def _matches_route(template: str, path: str) -> bool:
    escaped = re.escape(template)
    pattern = re.sub(r"\\\{[^/{}]+\\\}", r"[^/]+", escaped)
    return re.fullmatch(pattern, path) is not None
