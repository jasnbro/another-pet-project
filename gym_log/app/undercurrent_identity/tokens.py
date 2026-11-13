"""Random tokens and ids. Raw tokens go to the browser or into a link once;
only their SHA-256 hash is ever stored."""
import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def new_id() -> str:
    return secrets.token_hex(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
