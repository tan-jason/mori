"""Account-owned insight inspection, correction, and deletion."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from mori.api.auth import session_token, verify_csrf
from mori.api.contracts import mutation_headers
from mori.modules.learning.learner_file_routes import (
    EditLearnerFileEntryRequest,
    _decode_cursor,
    _encode_cursor,
    _user_id,
    _version,
)
from mori.modules.learning.user_insights import UserInsightEntry, UserInsightService

router = APIRouter(prefix="/api/v1/user-insights", tags=["user-insights"])


class UserInsightEntryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: UUID
    kind: Literal["insight"] = "insight"
    text: str
    origin: Literal["capture", "learner_edit"]
    version: int
    source_session_id: UUID = Field(alias="sourceSessionId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    expires_at: datetime | None = Field(alias="expiresAt")
    temporal_context: str | None = Field(default=None, alias="temporalContext")

    @classmethod
    def from_domain(cls, entry: UserInsightEntry) -> UserInsightEntryResponse:
        return cls(
            id=entry.id,
            text=entry.text,
            origin=cast(Literal["capture", "learner_edit"], entry.origin),
            version=entry.version,
            sourceSessionId=entry.source_session_id,
            createdAt=entry.created_at,
            updatedAt=entry.updated_at,
            expiresAt=entry.expires_at,
            temporalContext=entry.temporal_context,
        )


class UserInsightsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    entries: list[UserInsightEntryResponse]
    next_cursor: str | None = Field(alias="nextCursor")


def _service(request: Request) -> UserInsightService:
    return cast(UserInsightService, request.app.state.user_insight_service)


@router.get("", response_model=UserInsightsResponse)
async def list_insights(
    request: Request, response: Response, cursor: str | None = None
) -> UserInsightsResponse:
    page = await _service(request).list(
        user_id=await _user_id(request), before=_decode_cursor(cursor)
    )
    response.headers["Cache-Control"] = "no-store"
    return UserInsightsResponse(
        entries=[UserInsightEntryResponse.from_domain(entry) for entry in page.entries],
        nextCursor=_encode_cursor(page.next_cursor),
    )


@router.patch(
    "/{entry_id}",
    response_model=UserInsightEntryResponse,
    openapi_extra=mutation_headers("If-Match"),
)
async def edit_insight(
    request: Request,
    response: Response,
    entry_id: UUID,
    body: EditLearnerFileEntryRequest,
    if_match: str | None = Header(default=None, include_in_schema=False),
) -> UserInsightEntryResponse:
    verify_csrf(request, session_token(request))
    entry = await _service(request).edit(
        user_id=await _user_id(request),
        entry_id=entry_id,
        expected_version=_version(if_match),
        text=body.text,
    )
    response.headers["ETag"] = f'"{entry.version}"'
    response.headers["Cache-Control"] = "no-store"
    return UserInsightEntryResponse.from_domain(entry)


@router.delete("/{entry_id}", status_code=204, openapi_extra=mutation_headers("If-Match"))
async def delete_insight(
    request: Request,
    response: Response,
    entry_id: UUID,
    if_match: str | None = Header(default=None, include_in_schema=False),
) -> None:
    verify_csrf(request, session_token(request))
    await _service(request).delete(
        user_id=await _user_id(request), entry_id=entry_id, expected_version=_version(if_match)
    )
    response.headers["Cache-Control"] = "no-store"
