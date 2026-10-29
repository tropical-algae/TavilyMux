from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tavily_mux.persistence.models import ProxyAttempt, ProxyRequest
from tavily_mux.services.control.models import (
    PaginatedLogs,
    ProxyAttemptResponse,
    ProxyLogResponse,
)


def list_proxy_logs(
    session: Session,
    *,
    page: int,
    page_size: int,
    pool_id: str | None,
    status_code: int | None,
    key_id: str | None = None,
    success: bool | None = None,
    retried: bool | None = None,
    request_id: str | None = None,
    time_from: datetime | None = None,
    time_to: datetime | None = None,
) -> PaginatedLogs:
    filters = []
    if pool_id is not None:
        filters.append(ProxyRequest.pool_id == pool_id)
    if status_code is not None:
        filters.append(ProxyRequest.status_code == status_code)
    if key_id is not None:
        filters.append(
            ProxyRequest.id.in_(
                select(ProxyAttempt.request_id).where(ProxyAttempt.key_id == key_id)
            )
        )
    if success is True:
        filters.append(ProxyRequest.status_code.between(200, 299))
    elif success is False:
        filters.append(
            or_(
                ProxyRequest.status_code.is_(None),
                ProxyRequest.status_code < 200,
                ProxyRequest.status_code >= 300,
            )
        )
    if retried is True:
        filters.append(ProxyRequest.attempt_count > 1)
    elif retried is False:
        filters.append(ProxyRequest.attempt_count <= 1)
    if request_id:
        pattern = f"%{request_id.strip()}%"
        filters.append(
            or_(
                ProxyRequest.id.ilike(pattern),
                ProxyRequest.external_request_id.ilike(pattern),
            )
        )
    if time_from is not None:
        filters.append(ProxyRequest.created_at >= time_from)
    if time_to is not None:
        filters.append(ProxyRequest.created_at <= time_to)
    total = session.scalar(select(func.count()).select_from(ProxyRequest).where(*filters)) or 0
    requests = session.scalars(
        select(ProxyRequest)
        .where(*filters)
        .order_by(ProxyRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    request_ids = [request.id for request in requests]
    attempts_by_request: dict[str, list[ProxyAttemptResponse]] = {}
    if request_ids:
        attempts = session.scalars(
            select(ProxyAttempt)
            .where(ProxyAttempt.request_id.in_(request_ids))
            .order_by(ProxyAttempt.request_id, ProxyAttempt.attempt_no)
        ).all()
        for attempt in attempts:
            attempts_by_request.setdefault(attempt.request_id, []).append(
                ProxyAttemptResponse(
                    attempt_no=attempt.attempt_no,
                    key_id=attempt.key_id,
                    status_code=attempt.status_code,
                    latency_ms=attempt.latency_ms,
                    error_type=attempt.error_type,
                )
            )
    items = [
        ProxyLogResponse(
            id=request.id,
            pool_id=request.pool_id,
            final_key_id=request.final_key_id,
            created_at=request.created_at,
            completed_at=request.completed_at,
            status_code=request.status_code,
            latency_ms=request.latency_ms,
            attempt_count=request.attempt_count,
            method=request.method,
            endpoint=request.endpoint,
            path=request.path,
            credits=request.credits,
            error_type=request.error_type,
            external_request_id=request.external_request_id,
            attempts=attempts_by_request.get(request.id, []),
        )
        for request in requests
    ]
    return PaginatedLogs(items=items, total=total, page=page, page_size=page_size)
