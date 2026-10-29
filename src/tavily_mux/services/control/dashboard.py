from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tavily_mux.domain.enums import KeyStatus
from tavily_mux.persistence.models import Pool, ProxyRequest, TavilyKey
from tavily_mux.runtime.registry import ROUTABLE_STATUSES, RuntimeRegistry
from tavily_mux.services.control.models import DashboardAlert, DashboardResponse
from tavily_mux.services.control.shared import key_is_routable, key_quota, pool_status


def dashboard(
    session: Session,
    *,
    dropped_log_events: int = 0,
    runtime: RuntimeRegistry | None = None,
) -> DashboardResponse:
    pools = session.scalars(select(Pool)).all()
    keys = session.scalars(select(TavilyKey)).all()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    requests_today = (
        session.scalar(
            select(func.count())
            .select_from(ProxyRequest)
            .where(ProxyRequest.created_at >= today)
        )
        or 0
    )
    successes_today = (
        session.scalar(
            select(func.count())
            .select_from(ProxyRequest)
            .where(ProxyRequest.created_at >= today, ProxyRequest.status_code.between(200, 299))
        )
        or 0
    )
    average_latency = session.scalar(
        select(func.avg(ProxyRequest.latency_ms)).where(ProxyRequest.created_at >= today)
    )
    credits_today = session.scalar(
        select(func.sum(ProxyRequest.credits)).where(ProxyRequest.created_at >= today)
    )
    keys_by_pool: dict[str, list[TavilyKey]] = {}
    for key in keys:
        keys_by_pool.setdefault(key.pool_id, []).append(key)
    pool_statuses = {
        pool.id: pool_status(pool, keys_by_pool.get(pool.id, [])) for pool in pools
    }
    healthy_pool_count = sum(
        current in {"normal", "degraded"} for current in pool_statuses.values()
    )
    if runtime is None:
        available_key_count = sum(key_is_routable(key) for key in keys)
        remaining_values = [
            quota.effective_remaining
            for key in keys
            if key_is_routable(key)
            and (quota := key_quota(key)).effective_remaining is not None
        ]
    else:
        runtime_keys = [
            key for pool in runtime.snapshot.pools.values() for key in pool.keys.values()
        ]
        available_runtime = [
            key
            for key in runtime_keys
            if key.enabled and key.status in ROUTABLE_STATUSES and key.remaining != 0
        ]
        available_key_count = len(available_runtime)
        remaining_values = [
            remaining for key in available_runtime if (remaining := key.remaining) is not None
        ]
    alerts = [
        DashboardAlert(
            severity="critical",
            code="pool_unavailable",
            message=f"账号池“{pool.name}”当前没有可用 Key",
            pool_id=pool.id,
        )
        for pool in pools
        if pool_statuses[pool.id] == "unavailable"
    ]
    alert_statuses = {
        KeyStatus.INVALID.value: ("critical", "key_invalid", "鉴权失败"),
        KeyStatus.EXHAUSTED.value: ("critical", "key_exhausted", "额度已耗尽"),
        KeyStatus.RATE_LIMITED.value: ("warning", "key_rate_limited", "正在被限流"),
        KeyStatus.LOW_QUOTA.value: ("warning", "key_low_quota", "剩余额度偏低"),
        KeyStatus.CHECK_FAILED.value: ("warning", "key_check_failed", "额度检测失败"),
    }
    for key in keys:
        alert = alert_statuses.get(key.status)
        if key.enabled and alert is not None:
            severity, code, description = alert
            alerts.append(
                DashboardAlert(
                    severity=severity,
                    code=code,
                    message=f"Tavily Key“{key.name}”{description}",
                    pool_id=key.pool_id,
                    key_id=key.id,
                )
            )
    if dropped_log_events:
        alerts.insert(
            0,
            DashboardAlert(
                severity="critical",
                code="request_logs_dropped",
                message=f"事件队列已丢弃 {dropped_log_events} 条请求日志",
            ),
        )
    return DashboardResponse(
        pool_count=len(pools),
        healthy_pool_count=healthy_pool_count,
        normal_pool_count=sum(status == "normal" for status in pool_statuses.values()),
        degraded_pool_count=sum(status == "degraded" for status in pool_statuses.values()),
        unavailable_pool_count=sum(
            status == "unavailable" for status in pool_statuses.values()
        ),
        disabled_pool_count=sum(status == "disabled" for status in pool_statuses.values()),
        key_count=len(keys),
        available_key_count=available_key_count,
        estimated_remaining=max(remaining_values) if remaining_values else None,
        requests_today=requests_today,
        successes_today=successes_today,
        credits_today=int(credits_today) if credits_today is not None else None,
        success_rate=(successes_today / requests_today * 100 if requests_today else 0),
        average_latency_ms=float(average_latency) if average_latency is not None else None,
        dropped_log_events=dropped_log_events,
        alerts=alerts[:20],
    )
