from pydantic import BaseModel


class ConnectionTestResponse(BaseModel):
    ok: bool
    latency_ms: float
    status_code: int | None
    proxy_configured: bool
    message: str
