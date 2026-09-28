"""Authentication domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GoogleClaims:
    subject: str
    email: str
    email_verified: bool
    display_name: str


@dataclass(frozen=True, slots=True)
class OAuthLoginAttempt:
    nonce: str
    code_verifier: str
    return_path: str


@dataclass(frozen=True, slots=True)
class ApplicationSession:
    id: UUID
    user_id: UUID
    expires_at: datetime
