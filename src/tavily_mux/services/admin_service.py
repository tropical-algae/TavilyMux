import secrets

from sqlalchemy.orm import Session

from tavily_mux.common.config import Settings
from tavily_mux.common.security import (
    SecretManager,
    generate_admin_secret,
    hash_admin_secret,
    verify_admin_secret,
)
from tavily_mux.persistence.initialize import initialize_database
from tavily_mux.persistence.models import AdminCredential
from tavily_mux.services.errors import AuthenticationError


def reset_admin_secret(settings: Settings, requested_secret: str | None = None) -> str:
    secret = requested_secret or generate_admin_secret()
    if len(secret) < 12:
        raise ValueError("The management key must contain at least 12 characters")

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    initialization = initialize_database(
        settings.database_url,
        auto_migrate=settings.AUTO_MIGRATE,
    )
    database = initialization.database
    try:
        SecretManager.load(
            settings.DATA_DIR,
            settings.MASTER_KEY,
            refuse_generation=initialization.schema_existed,
        )
        with database.session() as session:
            admin = session.get(AdminCredential, 1)
            if admin is None:
                admin = AdminCredential(id=1, secret_hash=hash_admin_secret(secret))
                session.add(admin)
            else:
                admin.secret_hash = hash_admin_secret(secret)
                admin.session_version += 1
            session.commit()
    finally:
        database.close()
    return secret


def authenticate_admin(session: Session, secret: str) -> AdminCredential:
    admin = session.get(AdminCredential, 1)
    if admin is None or not verify_admin_secret(secret, admin.secret_hash):
        raise AuthenticationError("Invalid management key")
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
