"""Public session creation and status response."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mori.modules.sessions.application import SessionView
from mori.modules.sessions.domain import normalize_requested_words, normalize_topic


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_profile_id: UUID = Field(alias="languageProfileId")
    topic: str | None = Field(default=None, max_length=160)
    requested_words: tuple[Annotated[str, Field(min_length=1, max_length=48)], ...] = Field(
        default=(), alias="requestedWords", max_length=8
    )

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str | None) -> str | None:
        return normalize_topic(value)

    @field_validator("requested_words")
    @classmethod
    def clean_words(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_requested_words(value)


class PlanPreviewResponse(BaseModel):
    objectives: list[str]


class SessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    state: str
    row_version: int = Field(alias="rowVersion")
    connected_limit_ms: int = Field(alias="connectedLimitMs")
    connected_ms: int = Field(alias="connectedMs")
    reservation_expires_at: datetime = Field(alias="reservationExpiresAt")
    objective: str
    mode: str
    plan_preview: PlanPreviewResponse = Field(alias="planPreview")
    created_at: datetime = Field(alias="createdAt")

    @classmethod
    def from_view(cls, view: SessionView) -> SessionResponse:
        return cls(
            id=view.id,
            state=view.state,
            rowVersion=view.row_version,
            connectedLimitMs=view.connected_limit_ms,
            connectedMs=view.connected_ms,
            reservationExpiresAt=view.reservation_expires_at,
            objective=view.objective,
            mode=view.mode,
            planPreview=PlanPreviewResponse(objectives=list(view.objectives)),
            createdAt=view.created_at,
        )
