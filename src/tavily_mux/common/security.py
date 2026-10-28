import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from tavily_mux.common.time import utc_now

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class SecretError(ValueError):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_admin_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        secret.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(salt)}${_b64encode(digest)}"


def verify_admin_secret(secret: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", maxsplit=5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            secret.encode(),
            salt=_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(digest, _b64decode(expected))
    except (TypeError, ValueError):
        return False


class SecretManager:
    def __init__(self, key: bytes) -> None:
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as error:
            raise SecretError("Invalid master key") from error
        self._key = key
        self._pepper = hashlib.sha256(key + b":tavily-mux-pepper").digest()

    @classmethod
    def load(
        cls,
        data_dir: Path,
        configured_key: str | None,
        *,
        refuse_generation: bool = False,
    ) -> "SecretManager":
        key_file = data_dir / "master.key"
        if configured_key:
            encoded = configured_key.encode()
            manager = cls(encoded)
            if key_file.exists():
                if not hmac.compare_digest(key_file.read_bytes().strip(), encoded):
                    raise SecretError("Configured master key does not match persisted key")
            else:
                cls._write_key(key_file, encoded)
            return manager
        if key_file.exists():
            return cls(key_file.read_bytes().strip())
        if refuse_generation:
            raise SecretError("Master key is missing for an existing database")

        key = Fernet.generate_key()
        cls._write_key(key_file, key)
        return cls(key)

    @staticmethod
    def _write_key(key_file: Path, key: bytes) -> None:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key + b"\n")
        key_file.chmod(0o600)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError) as error:
            raise SecretError("Unable to decrypt stored secret") from error

    def digest(self, value: str, *, purpose: str) -> str:
        return hmac.new(
            self._pepper,
            f"{purpose}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def create_session(self, session_version: int, max_age_seconds: int) -> str:
        payload = {
            "exp": int((utc_now() + timedelta(seconds=max_age_seconds)).timestamp()),
            "nonce": secrets.token_urlsafe(12),
            "version": session_version,
        }
        encoded = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signature = self.digest(encoded, purpose="admin-session")
        return f"{encoded}.{signature}"

    def verify_session(self, token: str) -> dict[str, Any] | None:
        try:
            encoded, signature = token.split(".", maxsplit=1)
            expected = self.digest(encoded, purpose="admin-session")
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_b64decode(encoded))
            if not isinstance(payload, dict) or int(payload["exp"]) <= int(
                utc_now().timestamp()
            ):
                return None
            return payload
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None


def generate_admin_secret() -> str:
    return secrets.token_urlsafe(24)


def generate_relay_key() -> tuple[str, str, str]:
    key_id = secrets.token_hex(12)
    secret = secrets.token_urlsafe(32)
    return key_id, secret, f"tpool_{key_id}_{secret}"


def parse_relay_key(token: str) -> tuple[str, str] | None:
    prefix, separator, remainder = token.partition("_")
    key_id, second_separator, secret = remainder.partition("_")
    if prefix != "tpool" or not separator or not second_separator or not key_id or not secret:
        return None
    return key_id, secret
