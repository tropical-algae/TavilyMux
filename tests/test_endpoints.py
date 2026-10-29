import pytest
from pydantic import ValidationError

from tavily_mux.common.config import Settings
from tavily_mux.domain.endpoints import (
    CreditProfile,
    EndpointSettings,
    endpoint_specs,
    estimate_credits,
    streamed_request_id,
)


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
        [{"path": "/search", "method": "GET"}],
        [{"path": "/research/an-id"}],
        [{"path": "/usage"}],
        [{"path": "/api/custom"}],
        [{"path": "/pools/custom"}],
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


def test_disabled_endpoint_names_are_validated() -> None:
    with pytest.raises(ValidationError, match="unknown built-in endpoint"):
        EndpointSettings(disabled={"future"})


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
        '{"disabled":["map"],"custom":[{"path":"/future"}]}',
    )

    settings = Settings(_env_file=None)

    assert settings.ENDPOINTS.disabled == {"map"}
    assert settings.ENDPOINTS.custom[0].path == "/future"
