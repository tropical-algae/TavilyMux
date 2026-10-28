import hmac
from collections.abc import AsyncIterator

from fastapi import Cookie, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from tavily_mux.persistence.models import AdminCredential
from tavily_mux.services.bootstrap import ApplicationContext

SESSION_COOKIE = "tavily_mux_session"
CSRF_COOKIE = "tavily_mux_csrf"


def get_context(request: Request) -> ApplicationContext:
    context: ApplicationContext | None = request.app.state.context
    if context is None or not context.ready:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service is starting")
    return context


async def get_session(request: Request) -> AsyncIterator[Session]:
    context = get_context(request)
    with context.database.session() as session:
        yield session


async def require_admin(
    request: Request,
    tavily_mux_session: str | None = Cookie(default=None),
) -> AdminCredential:
    if not tavily_mux_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    context = get_context(request)
    payload = context.secrets.verify_session(tavily_mux_session)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    with context.database.session() as session:
        admin = session.get(AdminCredential, 1)
        if admin is None or payload.get("version") != admin.session_version:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been revoked")
        session.expunge(admin)
        return admin


async def require_csrf(
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
) -> None:
    if not csrf_header or not csrf_cookie or not hmac.compare_digest(csrf_header, csrf_cookie):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid CSRF token")
