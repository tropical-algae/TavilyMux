from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from tavily_mux.services.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    NotInitializedError,
    ServiceError,
)

_STATUS_CODES: dict[type[ServiceError], int] = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    ConflictError: status.HTTP_409_CONFLICT,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    NotInitializedError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, _service_error_handler)


async def _service_error_handler(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ServiceError):
        raise error
    status_code = _STATUS_CODES.get(type(error), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content={"detail": str(error)})
