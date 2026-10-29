from fastapi import APIRouter, Request, Response

from tavily_mux.api.data_plane.handler import disabled_response, relay
from tavily_mux.common.config import EndpointSettings
from tavily_mux.domain.endpoints import EndpointSpec
from tavily_mux.integrations.tavily.endpoint_catalog import (
    BUILTIN_ENDPOINTS,
    endpoint_specs,
)


def create_router(settings: EndpointSettings) -> APIRouter:
    router = APIRouter()
    for route_index, spec in enumerate(endpoint_specs(settings)):
        extra = None
        if spec.method == "POST":
            extra = {
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            }
        router.add_api_route(
            spec.path,
            _handler_for(spec),
            methods=[spec.method],
            response_class=Response,
            name=f"relay_{spec.id}_{spec.method.lower()}_{route_index}",
            openapi_extra=extra,
        )

    for spec in BUILTIN_ENDPOINTS:
        if spec.id not in settings.disabled:
            continue
        router.add_api_route(
            spec.path,
            disabled_response,
            methods=[spec.method],
            include_in_schema=False,
            name=f"disabled_{spec.id}_{spec.method.lower()}",
        )
    return router


def _handler_for(spec: EndpointSpec):
    async def endpoint(request: Request) -> Response:
        return await relay(request, spec)

    return endpoint
