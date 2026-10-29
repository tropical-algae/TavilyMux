from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from tavily_mux.common.config import Settings
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.models import AdminCredential
from tavily_mux.services.admin_service import reset_admin_secret


def test_reset_admin_secret_creates_and_rotates_credential(tmp_path: Path) -> None:
    settings = Settings(
        DATA_DIR=tmp_path,
        MASTER_KEY=Fernet.generate_key().decode(),
    )

    assert reset_admin_secret(settings, "first-admin-secret") == "first-admin-secret"
    database = Database(settings.database_url)
    with database.session() as session:
        first = session.get(AdminCredential, 1)
        assert first is not None
        original_hash = first.secret_hash
        assert first.session_version == 1

    assert reset_admin_secret(settings, "second-admin-secret") == "second-admin-secret"
    with database.session() as session:
        second = session.get(AdminCredential, 1)
        assert second is not None
        assert second.secret_hash != original_hash
        assert second.session_version == 2
    database.close()


def test_reset_admin_secret_rejects_short_value(tmp_path: Path) -> None:
    settings = Settings(DATA_DIR=tmp_path)

    with pytest.raises(ValueError, match="at least 12"):
        reset_admin_secret(settings, "too-short")
