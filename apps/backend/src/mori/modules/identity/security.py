"""Token creation and one-way derivation for identity flows."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def random_token(byte_count: int = 32) -> str:
    return secrets.token_urlsafe(byte_count)


def keyed_digest(token: str, key: str, *, purpose: str) -> str:
    message = f"{purpose}:{token}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def csrf_token(session_token: str, key: str) -> str:
    return keyed_digest(session_token, key, purpose="csrf")


def tokens_match(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
