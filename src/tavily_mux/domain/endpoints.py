from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class BuiltinEndpoint(StrEnum):
    SEARCH = "search"
    EXTRACT = "extract"
    CRAWL = "crawl"
    MAP = "map"
    RESEARCH = "research"
    FEEDBACK = "feedback"


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
