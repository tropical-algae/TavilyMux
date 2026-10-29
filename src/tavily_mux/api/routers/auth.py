from fastapi import APIRouter, Request, Response, status

from tavily_mux.api.dependencies import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AdminDep,
    CsrfDep,
    SessionDep,
    get_context,
)
from tavily_mux.api.schemas.auth import (
    AuthStatus,
    ChangeAdminSecretRequest,
    LoginRequest,
    LoginResponse,
)
from tavily_mux.services import admin_service
from tavily_mux.services.bootstrap import ApplicationContext

router = APIRouter()


def _set_auth_cookies(
    response: Response,
    context: ApplicationContext,
    *,
    session_token: str,
    csrf_token: str,
    remember: bool,
) -> None:
    settings = context.settings
    max_age = settings.SESSION_MAX_AGE_SECONDS if remember else None
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> LoginResponse:
    context = get_context(request)
    admin = admin_service.authenticate_admin(session, payload.secret)
    csrf_token = admin_service.generate_csrf_token()
    session_token = context.secrets.create_session(
        admin.session_version,
        context.settings.SESSION_MAX_AGE_SECONDS,
    )
    _set_auth_cookies(
        response,
        context,
        session_token=session_token,
        csrf_token=csrf_token,
        remember=payload.remember,
    )
    return LoginResponse(csrf_token=csrf_token)


@router.get("/me", response_model=AuthStatus)
async def auth_status(_: AdminDep) -> AuthStatus:
    return AuthStatus()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, _: AdminDep, __: CsrfDep) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/secret", status_code=status.HTTP_204_NO_CONTENT)
async def change_admin_secret(
    payload: ChangeAdminSecretRequest,
    response: Response,
    session: SessionDep,
    _: AdminDep,
    __: CsrfDep,
) -> Response:
    admin_service.change_admin_secret(
        session,
        current_secret=payload.current_secret,
        new_secret=payload.new_secret,
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
