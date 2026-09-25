"""Public session creation and status response."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mori.modules.sessions.application import SessionView


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_profile_id: UUID = Field(alias="languageProfileId")


class SessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    state: str
    row_version: int = Field(alias="rowVersion")
    connected_limit_ms: int = Field(alias="connectedLimitMs")
    connected_ms: int = Field(alias="connectedMs")
    reservation_expires_at: datetime = Field(alias="reservationExpiresAt")
    objective: str
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
            createdAt=view.created_at,
        )
