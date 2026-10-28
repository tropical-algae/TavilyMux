from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from tavily_mux.common.security import (
    SecretError,
    SecretManager,
    generate_admin_secret,
    generate_relay_key,
    hash_admin_secret,
    parse_relay_key,
    verify_admin_secret,
)


def test_admin_secret_hash_round_trip() -> None:
    encoded = hash_admin_secret("correct horse battery staple")

    assert verify_admin_secret("correct horse battery staple", encoded)
    assert not verify_admin_secret("wrong", encoded)
    assert not verify_admin_secret("value", "invalid")


def test_secret_manager_persists_generated_key(tmp_path: Path) -> None:
    first = SecretManager.load(tmp_path, None)
    encrypted = first.encrypt("sensitive-value")
    second = SecretManager.load(tmp_path, None)

    assert second.decrypt(encrypted) == "sensitive-value"
    assert (tmp_path / "master.key").stat().st_mode & 0o777 == 0o600


def test_secret_manager_uses_configured_key(tmp_path: Path) -> None:
    key = Fernet.generate_key().decode()
    manager = SecretManager.load(tmp_path, key)

    assert manager.decrypt(manager.encrypt("value")) == "value"
    assert (tmp_path / "master.key").read_text().strip() == key

    with pytest.raises(SecretError, match="does not match"):
        SecretManager.load(tmp_path, Fernet.generate_key().decode())


def test_secret_manager_refuses_to_replace_missing_key(tmp_path: Path) -> None:
    with pytest.raises(SecretError, match="missing"):
        SecretManager.load(tmp_path, None, refuse_generation=True)


def test_secret_manager_rejects_invalid_values() -> None:
    with pytest.raises(SecretError, match="Invalid master key"):
        SecretManager(b"invalid")

    manager = SecretManager(Fernet.generate_key())
    with pytest.raises(SecretError, match="Unable to decrypt"):
        manager.decrypt("invalid")


def test_session_signing_and_expiration() -> None:
    manager = SecretManager(Fernet.generate_key())
    token = manager.create_session(session_version=4, max_age_seconds=60)
    payload = manager.verify_session(token)

    assert payload is not None
    assert payload["version"] == 4
    assert manager.verify_session(token + "tampered") is None
    assert manager.verify_session(manager.create_session(1, -1)) is None
    assert manager.verify_session("invalid") is None


def test_relay_key_generation_and_parsing() -> None:
    key_id, secret, token = generate_relay_key()

    assert parse_relay_key(token) == (key_id, secret)
    assert parse_relay_key("invalid") is None
    assert len(generate_admin_secret()) >= 24
