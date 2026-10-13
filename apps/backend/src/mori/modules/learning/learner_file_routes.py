"""Profile-scoped inspection, correction, and deletion of captured entries."""

from __future__ import annotations

import re
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mori.api.auth import session_token, verify_csrf
from mori.api.contracts import mutation_headers
from mori.modules.learner_profiles.errors import InvalidPrecondition, PreconditionRequired
from mori.modules.learning.learner_file import (
    InvalidLearnerFileCursor,
    LearnerFileEntry,
    LearnerFileService,
)
from mori.modules.user.application import UserService

router = APIRouter(
    prefix="/api/v1/language-profiles/{profile_id}/learner-file", tags=["learner-file"]
)
_ETAG_PATTERN = re.compile(r'^"([1-9][0-9]*)"$')


class LearnerFileEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    kind: Literal["learning", "insight"]
    text: str
    origin: Literal["capture", "learner_edit"]
    version: int
    source_session_id: UUID | None = Field(alias="sourceSessionId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    expires_at: datetime | None = Field(alias="expiresAt")

    @classmethod
    def from_domain(cls, entry: LearnerFileEntry) -> LearnerFileEntryResponse:
        return cls(
            id=entry.id,
            kind=cast(Literal["learning", "insight"], entry.kind),
            text=entry.text,
            origin=cast(Literal["capture", "learner_edit"], entry.origin),
            version=entry.version,
            sourceSessionId=entry.source_session_id,
            createdAt=entry.created_at,
            updatedAt=entry.updated_at,
            expiresAt=entry.expires_at,
        )


class LearnerFileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    entries: list[LearnerFileEntryResponse]
    next_cursor: str | None = Field(alias="nextCursor")


class EditLearnerFileEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=240)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("text is required")
        return normalized


def _service(request: Request) -> LearnerFileService:
    return cast(LearnerFileService, request.app.state.learner_file_service)


async def _user_id(request: Request) -> UUID:
    learner = await cast(UserService, request.app.state.user_service).current_learner(
        session_token=session_token(request)
    )
    return learner.user_id


def _version(if_match: str | None) -> int:
    if if_match is None:
        raise PreconditionRequired
    match = _ETAG_PATTERN.fullmatch(if_match.strip())
    if match is None:
        raise InvalidPrecondition
    return int(match.group(1))


def _decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    if not cursor or len(cursor) > 128:
        raise InvalidLearnerFileCursor
    try:
        stamp, entry_id = urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
        created_at = datetime.fromisoformat(stamp)
        if created_at.tzinfo is None:
            raise ValueError("cursor time must have timezone")
        return created_at, UUID(entry_id)
    except (ValueError, UnicodeDecodeError, Base64Error) as error:
        raise InvalidLearnerFileCursor from error


def _encode_cursor(cursor: tuple[datetime, UUID] | None) -> str | None:
    if cursor is None:
        return None
    return urlsafe_b64encode(f"{cursor[0].isoformat()}|{cursor[1]}".encode()).decode().rstrip("=")


@router.get("", response_model=LearnerFileResponse)
async def list_entries(
    request: Request,
    response: Response,
    profile_id: UUID,
    cursor: str | None = None,
) -> LearnerFileResponse:
    page = await _service(request).list(
        user_id=await _user_id(request), profile_id=profile_id, before=_decode_cursor(cursor)
    )
    response.headers["Cache-Control"] = "no-store"
    return LearnerFileResponse(
        entries=[LearnerFileEntryResponse.from_domain(entry) for entry in page.entries],
        nextCursor=_encode_cursor(page.next_cursor),
    )


@router.patch(
    "/{entry_id}",
    response_model=LearnerFileEntryResponse,
    openapi_extra=mutation_headers("If-Match"),
)
async def edit_entry(
    request: Request,
    response: Response,
    profile_id: UUID,
    entry_id: UUID,
    body: EditLearnerFileEntryRequest,
    if_match: str | None = Header(default=None, include_in_schema=False),
) -> LearnerFileEntryResponse:
    verify_csrf(request, session_token(request))
    entry = await _service(request).edit(
        user_id=await _user_id(request),
        profile_id=profile_id,
        entry_id=entry_id,
        expected_version=_version(if_match),
        text=body.text,
    )
    response.headers["ETag"] = f'"{entry.version}"'
    response.headers["Cache-Control"] = "no-store"
    return LearnerFileEntryResponse.from_domain(entry)


@router.delete("/{entry_id}", status_code=204, openapi_extra=mutation_headers("If-Match"))
async def delete_entry(
    request: Request,
    response: Response,
    profile_id: UUID,
    entry_id: UUID,
    if_match: str | None = Header(default=None, include_in_schema=False),
) -> None:
    verify_csrf(request, session_token(request))
    await _service(request).delete(
        user_id=await _user_id(request),
        profile_id=profile_id,
        entry_id=entry_id,
        expected_version=_version(if_match),
    )
    response.headers["Cache-Control"] = "no-store"
