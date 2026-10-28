import pytest

from tavily_mux.domain.enums import KeyStatus, QuotaBottleneck
from tavily_mux.domain.quota import calculate_quota, status_for_quota


def test_unlimited_key_falls_back_to_account_quota() -> None:
    quota = calculate_quota(
        key_usage=17,
        key_limit=None,
        account_plan_usage=125,
        account_plan_limit=1000,
        paygo_usage=0,
        paygo_limit=None,
    )

    assert quota.key_remaining is None
    assert quota.account_remaining == 875
    assert quota.effective_remaining == 875
    assert quota.bottleneck is QuotaBottleneck.ACCOUNT
    assert status_for_quota(quota) is KeyStatus.AVAILABLE


def test_account_exhaustion_wins_even_when_key_has_capacity() -> None:
    quota = calculate_quota(
        key_usage=10,
        key_limit=500,
        account_plan_usage=1000,
        account_plan_limit=1000,
        paygo_usage=0,
        paygo_limit=None,
    )

    assert quota.key_remaining == 490
    assert quota.account_remaining == 0
    assert quota.effective_remaining == 0
    assert quota.bottleneck is QuotaBottleneck.ACCOUNT
    assert status_for_quota(quota) is KeyStatus.EXHAUSTED


def test_known_zero_constraint_wins_over_an_unknown_constraint() -> None:
    quota = calculate_quota(
        key_usage=None,
        key_limit=500,
        account_plan_usage=1000,
        account_plan_limit=1000,
        paygo_usage=0,
        paygo_limit=None,
    )

    assert quota.effective_remaining == 0
    assert quota.bottleneck is QuotaBottleneck.ACCOUNT
    assert status_for_quota(quota) is KeyStatus.EXHAUSTED


def test_key_limit_wins_when_it_is_more_restrictive() -> None:
    quota = calculate_quota(
        key_usage=95,
        key_limit=100,
        account_plan_usage=100,
        account_plan_limit=1000,
        paygo_usage=0,
        paygo_limit=None,
    )

    assert quota.key_remaining == 5
    assert quota.account_remaining == 900
    assert quota.effective_remaining == 5
    assert quota.bottleneck is QuotaBottleneck.KEY
    assert status_for_quota(quota) is KeyStatus.LOW_QUOTA


def test_paygo_extends_account_capacity_after_plan_credits() -> None:
    quota = calculate_quota(
        key_usage=1000,
        key_limit=None,
        account_plan_usage=1000,
        account_plan_limit=1000,
        paygo_usage=25,
        paygo_limit=100,
    )

    assert quota.account_plan_remaining == 0
    assert quota.paygo_remaining == 75
    assert quota.account_remaining == 75
    assert quota.effective_remaining == 75
    assert quota.effective_limit == 1100
    assert status_for_quota(quota) is KeyStatus.LOW_QUOTA


@pytest.mark.parametrize(
    ("key_usage", "key_limit", "plan_usage", "plan_limit"),
    [
        (None, 100, 10, 1000),
        (10, None, None, 1000),
        (10, None, None, None),
    ],
)
def test_unknown_hard_constraint_is_not_invented_as_capacity(
    key_usage: int | None,
    key_limit: int | None,
    plan_usage: int | None,
    plan_limit: int | None,
) -> None:
    quota = calculate_quota(
        key_usage=key_usage,
        key_limit=key_limit,
        account_plan_usage=plan_usage,
        account_plan_limit=plan_limit,
        paygo_usage=None,
        paygo_limit=None,
    )

    assert quota.effective_remaining is None
    assert quota.bottleneck is QuotaBottleneck.UNKNOWN
