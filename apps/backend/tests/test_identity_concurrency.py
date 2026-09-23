"""Adversarial identity provisioning tests against PostgreSQL."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from mori.modules.identity.application import IdentityService


@pytest.mark.asyncio
async def test_concurrent_sign_ins_create_one_identity_and_two_sessions(
    app: FastAPI,
    database_url: str,
) -> None:
    service: IdentityService = app.state.identity_service
    starts = await asyncio.gather(
        service.start_google_sign_in(return_path="/"),
        service.start_google_sign_in(return_path="/"),
    )
    states = [
        parse_qs(urlsplit(start.authorization_url).query)["state"][0] for start in starts
    ]

    await asyncio.gather(
        service.complete_google_sign_in(state=states[0], code="valid-code"),
        service.complete_google_sign_in(state=states[1], code="valid-code"),
    )

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            counts = {
                table: connection.scalar(text(f"SELECT count(*) FROM {table}"))
                for table in (
                    "users",
                    "external_identities",
                    "language_profiles",
                    "learner_preferences",
                    "grants",
                    "auth_sessions",
                )
            }
    finally:
        engine.dispose()

    assert counts == {
        "users": 1,
        "external_identities": 1,
        "language_profiles": 1,
        "learner_preferences": 1,
        "grants": 1,
        "auth_sessions": 2,
    }
