import pytest
from pydantic import ValidationError

from tavily_mux.api.router import create_router
from tavily_mux.common.config import EndpointSettings, Settings
from tavily_mux.domain.endpoints import (
    CreditProfile,
)
from tavily_mux.integrations.tavily.billing import estimate_credits
from tavily_mux.integrations.tavily.endpoint_catalog import endpoint_specs
from tavily_mux.integrations.tavily.protocol import streamed_request_id


def test_custom_endpoint_defaults_and_normalizes() -> None:
    settings = EndpointSettings(
        custom=[
            {"path": "/future-post/"},
            {"path": "/future-get", "method": "get"},
        ]
    )

    custom = [spec for spec in endpoint_specs(settings) if spec.id == "custom"]

    assert [(spec.path, spec.method) for spec in custom] == [
        ("/future-post", "POST"),
        ("/future-get", "GET"),
    ]


@pytest.mark.parametrize(
    "custom",
    [
        [{"path": "/same", "method": "GET"}, {"path": "/same", "method": "POST"}],
        [{"path": "/has/{parameter}"}],
        [{"path": "/has//repeated"}],
        [{"path": "/has/%2f/separator"}],
    ],
)
def test_custom_endpoint_rejects_conflicts_and_unsafe_paths(
    custom: list[dict[str, str]],
) -> None:
    with pytest.raises(ValidationError):
        EndpointSettings(disabled={"search"}, custom=custom)


@pytest.mark.parametrize(
    "path",
    [
        "/search",
        "/research/an-id",
        "/usage",
        "/api/custom",
        "/pools/custom",
    ],
)
def test_custom_endpoint_rejects_registered_route_conflicts(path: str) -> None:
    settings = Settings(ENDPOINTS={"CUSTOM": [{"PATH": path}]})

    with pytest.raises(ValueError, match=r"conflicts|reserved"):
        create_router(settings)


def test_disabled_endpoint_names_are_validated() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        EndpointSettings(disabled={"future"})


def test_endpoint_configuration_accepts_uppercase_aliases() -> None:
    settings = EndpointSettings.model_validate(
        {
            "DISABLED": ["SEARCH"],
            "CUSTOM": [{"PATH": "/future", "METHOD": "get"}],
        }
    )

    assert settings.disabled == {"search"}
    assert settings.custom[0].method == "GET"


def test_credit_estimates_use_endpoint_request_shape() -> None:
    assert estimate_credits(CreditProfile.SEARCH, b'{"search_depth":"advanced"}') == 2
    assert estimate_credits(CreditProfile.RESEARCH, b'{"model":"pro"}') == 15
    assert estimate_credits(CreditProfile.NONE, b"not-json") == 0
    assert estimate_credits(CreditProfile.UNKNOWN, b"not-json") == 1


def test_request_id_can_be_read_from_a_stream_event() -> None:
    body = b'event: metadata\ndata: {"request_id":"research-stream-1"}\n\n'

    assert streamed_request_id(body) == "research-stream-1"


def test_endpoint_registry_can_be_loaded_from_an_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TAVILY_MUX_ENDPOINTS",
        '{"DISABLED":["map"],"CUSTOM":[{"PATH":"/future"}]}',
    )

    settings = Settings(_env_file=None)

    assert settings.ENDPOINTS.disabled == {"map"}
    assert settings.ENDPOINTS.custom[0].path == "/future"
