from dataclasses import dataclass

from tavily_mux.domain.enums import KeyStatus, QuotaBottleneck


@dataclass(frozen=True, slots=True)
class QuotaState:
    """Normalized quota constraints returned by Tavily's ``/usage`` endpoint."""

    key_remaining: int | None
    account_plan_remaining: int | None
    paygo_remaining: int | None
    account_remaining: int | None
    effective_remaining: int | None
    effective_limit: int | None
    bottleneck: QuotaBottleneck


def calculate_quota(
    *,
    key_usage: int | None,
    key_limit: int | None,
    account_plan_usage: int | None,
    account_plan_limit: int | None,
    paygo_usage: int | None,
    paygo_limit: int | None,
) -> QuotaState:
    """Calculate the quota that can actually be routed through one API key.

    Tavily documents a null key limit as unlimited. Account plan quota is still
    a hard constraint, and configured PAYGO capacity extends the account quota
    after plan credits are consumed.
    """

    key_remaining = _remaining(key_usage, key_limit)
    plan_remaining = _remaining(account_plan_usage, account_plan_limit)
    paygo_remaining = _remaining(paygo_usage, paygo_limit)

    account_remaining = plan_remaining
    if account_remaining is not None and paygo_remaining is not None:
        account_remaining += paygo_remaining

    # A configured limit with no corresponding usage value is an unknown hard
    # constraint. Do not present or rank it as known capacity.
    key_constraint_unknown = key_limit is not None and key_remaining is None
    account_constraint_unknown = (
        account_plan_limit is not None and plan_remaining is None
    ) or (paygo_limit is not None and paygo_remaining is None)

    constraints: list[int] = []
    if key_limit is not None and key_remaining is not None:
        constraints.append(key_remaining)
    if account_remaining is not None:
        constraints.append(account_remaining)

    if 0 in constraints:
        effective_remaining = 0
    elif key_constraint_unknown or account_constraint_unknown:
        effective_remaining = None
    else:
        effective_remaining = min(constraints) if constraints else None

    account_limit = account_plan_limit
    if account_limit is not None and paygo_limit is not None:
        account_limit += paygo_limit
    limits = [value for value in (key_limit, account_limit) if value is not None]
    effective_limit = min(limits) if limits else None

    bottleneck = _bottleneck(
        effective_remaining=effective_remaining,
        key_remaining=key_remaining if key_limit is not None else None,
        account_remaining=account_remaining,
    )
    return QuotaState(
        key_remaining=key_remaining,
        account_plan_remaining=plan_remaining,
        paygo_remaining=paygo_remaining,
        account_remaining=account_remaining,
        effective_remaining=effective_remaining,
        effective_limit=effective_limit,
        bottleneck=bottleneck,
    )


def status_for_quota(quota: QuotaState) -> KeyStatus:
    if quota.effective_remaining == 0:
        return KeyStatus.EXHAUSTED
    if (
        quota.effective_remaining is not None
        and quota.effective_limit is not None
        and quota.effective_limit > 0
        and quota.effective_remaining <= max(int(quota.effective_limit * 0.1), 1)
    ):
        return KeyStatus.LOW_QUOTA
    return KeyStatus.AVAILABLE


def _remaining(usage: int | None, limit: int | None) -> int | None:
    if usage is None or limit is None:
        return None
    return max(limit - usage, 0)


def _bottleneck(
    *,
    effective_remaining: int | None,
    key_remaining: int | None,
    account_remaining: int | None,
) -> QuotaBottleneck:
    if effective_remaining is None:
        return QuotaBottleneck.UNKNOWN
    if key_remaining is None:
        return QuotaBottleneck.ACCOUNT
    if account_remaining is None:
        return QuotaBottleneck.KEY
    if key_remaining < account_remaining:
        return QuotaBottleneck.KEY
    if account_remaining < key_remaining:
        return QuotaBottleneck.ACCOUNT
    return QuotaBottleneck.BOTH
