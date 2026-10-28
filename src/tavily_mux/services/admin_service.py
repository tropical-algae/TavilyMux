import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from tavily_mux.common.security import hash_admin_secret, verify_admin_secret
from tavily_mux.persistence.models import AdminCredential


def authenticate_admin(session: Session, secret: str) -> AdminCredential:
    admin = session.get(AdminCredential, 1)
    if admin is None or not verify_admin_secret(secret, admin.secret_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid management key")
    return admin


def change_admin_secret(
    session: Session,
    *,
    current_secret: str,
    new_secret: str,
) -> AdminCredential:
    admin = authenticate_admin(session, current_secret)
    admin.secret_hash = hash_admin_secret(new_secret)
    admin.session_version += 1
    session.commit()
    session.refresh(admin)
    return admin


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)
