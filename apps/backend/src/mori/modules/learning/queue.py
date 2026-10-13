"""Procrastinate task registration and transactional enqueue."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import procrastinate
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from mori.config import Settings


class _QueueSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[6] / ".env", extra="ignore"
    )
    database_url: str = Field(default="postgresql://", alias="DATABASE_URL")


app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=_QueueSettings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    )
)


@app.task(name="mori.capture_session", retry=3, queue="analysis")
async def capture_session(run_id: str) -> None:
    from mori.db import create_engine, create_session_maker
    from mori.modules.learning.application import AnalysisService
    from mori.modules.learning.extractor import OpenAIExtractor

    settings = Settings()  # type: ignore[call-arg]
    if settings.openai_api_key is None:
        raise RuntimeError("analysis provider is not configured")
    engine = create_engine(settings.database_url)
    try:
        service = AnalysisService(
            session_maker=create_session_maker(engine),
            extractor=OpenAIExtractor(settings.openai_api_key.get_secret_value()),
            fact_digest_key=settings.session_signing_key.get_secret_value(),
        )
        await service.process(UUID(run_id))
    finally:
        await engine.dispose()


async def enqueue_capture(db: AsyncSession, run_id: UUID) -> None:
    connection = await db.connection()
    raw = await connection.get_raw_connection()
    await capture_session.configure(connection=raw.driver_connection).defer_async(
        run_id=str(run_id)
    )
