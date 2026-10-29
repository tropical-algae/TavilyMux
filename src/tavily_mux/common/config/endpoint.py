import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from tavily_mux.domain.endpoints import BuiltinEndpoint

_INVALID_PERCENT_ENCODING = re.compile(r"%(?:2e|2f|5c)", re.IGNORECASE)


def _uppercase_method(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


def _lowercase_items(value: object) -> object:
    if isinstance(value, (list, set, tuple)):
        return [item.lower() if isinstance(item, str) else item for item in value]
    return value


HttpMethod = Annotated[Literal["GET", "POST"], BeforeValidator(_uppercase_method)]


class CustomEndpoint(BaseModel):
    model_config = ConfigDict(
        alias_generator=str.upper,
        populate_by_name=True,
        extra="forbid",
    )

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
    model_config = ConfigDict(
        alias_generator=str.upper,
        populate_by_name=True,
        extra="forbid",
    )

    disabled: Annotated[set[BuiltinEndpoint], BeforeValidator(_lowercase_items)] = Field(
        default_factory=set
    )
    custom: list[CustomEndpoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_custom_paths(self) -> "EndpointSettings":
        paths = [endpoint.path for endpoint in self.custom]
        if len(paths) != len(set(paths)):
            raise ValueError("custom endpoint paths must be unique regardless of method")
        return self
