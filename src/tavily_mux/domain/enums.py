from enum import StrEnum


class KeyStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    LOW_QUOTA = "low_quota"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    INVALID = "invalid"
    CHECK_FAILED = "check_failed"
    DISABLED = "disabled"


class RoutingStrategy(StrEnum):
    MAX_REMAINING = "max_remaining"
    RANDOM = "random"


class QuotaBottleneck(StrEnum):
    UNKNOWN = "unknown"
    KEY = "key"
    ACCOUNT = "account"
    BOTH = "both"
