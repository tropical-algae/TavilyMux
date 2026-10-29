from mimetypes import guess_type
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from tavily_mux.integrations.tavily.endpoint_catalog import is_builtin_path


def create_router(
    web_root: Path | None,
    *,
    configured_data_paths: frozenset[str],
) -> APIRouter:
    router = APIRouter()
    if web_root is None or not (web_root / "index.html").is_file():
        return router

    resolved_root = web_root.resolve()
    web_files = {
        item.relative_to(resolved_root).as_posix(): (
            item.read_bytes(),
            guess_type(item.name)[0] or "application/octet-stream",
        )
        for item in resolved_root.rglob("*")
        if item.is_file()
    }

    @router.get("/{path:path}", include_in_schema=False)
    async def web_application(path: str) -> Response:
        request_path = f"/{path}"
        if path not in web_files and (
            is_builtin_path(request_path)
            or request_path in configured_data_paths
            or _is_reserved_path(request_path)
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        content, media_type = web_files.get(path, web_files["index.html"])
        cache_control = (
            "public, max-age=31536000, immutable"
            if path.startswith("assets/") and path in web_files
            else "no-cache"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Cache-Control": cache_control},
        )

    return router


def _is_reserved_path(path: str) -> bool:
    return path in {
        "/api",
        "/assets",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/livez",
        "/readyz",
        "/usage",
        "/org-usage",
    } or path.startswith(("/api/", "/assets/", "/docs/", "/redoc/"))
