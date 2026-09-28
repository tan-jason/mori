"""Explicit language profile commands and published pair queries."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256

from mori.modules.curriculum.domain import CoursePairView
from mori.modules.identity.application import IdentityService
from mori.modules.learner_profiles.domain import CreateProfile, PreferenceChanges
from mori.modules.learner_profiles.errors import InvalidOnboardingKey, UnsupportedLanguagePair
from mori.modules.users.application import current_learner_for_user
from mori.modules.users.domain import CurrentLearner
from mori.persistence.ports import UnitOfWorkFactory

_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{7,127}\Z")


class LearnerProfileService:
    def __init__(
        self, *, unit_of_work_factory: UnitOfWorkFactory, identity: IdentityService
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._identity = identity

    async def language_pairs(self) -> tuple[CoursePairView, ...]:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.curriculum.language_pairs()

    async def create_profile(
        self, *, session_token: str, idempotency_key: str, command: CreateProfile
    ) -> tuple[CurrentLearner, bool]:
        if not _KEY_PATTERN.fullmatch(idempotency_key):
            raise InvalidOnboardingKey
        key_digest = sha256(idempotency_key.encode("ascii")).hexdigest()
        payload_digest = sha256(
            json.dumps(asdict(command), sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        digest = self._identity.session_digest(session_token)
        now = datetime.now(UTC)
        async with self._unit_of_work_factory() as unit_of_work:
            user_id = await unit_of_work.identity.authenticated_user_id(
                token_digest=digest, now=now
            )
            await unit_of_work.users.active(user_id, lock=True)
            if await unit_of_work.profiles.replay_exists(
                user_id=user_id, key_digest=key_digest, payload_digest=payload_digest
            ):
                return await current_learner_for_user(unit_of_work, user_id), False
            if not await unit_of_work.curriculum.is_available(
                base_language_id=command.base_language_id,
                target_language_id=command.target_language_id,
            ):
                raise UnsupportedLanguagePair
            await unit_of_work.profiles.confirm(
                user_id=user_id,
                command=command,
                key_digest=key_digest,
                payload_digest=payload_digest,
                now=now,
            )
            await unit_of_work.users.complete_onboarding(user_id, now=now)
            return await current_learner_for_user(unit_of_work, user_id), True

    async def update_preferences(
        self,
        *,
        session_token: str,
        expected_version: int,
        changes: PreferenceChanges,
    ) -> CurrentLearner:
        digest = self._identity.session_digest(session_token)
        now = datetime.now(UTC)
        async with self._unit_of_work_factory() as unit_of_work:
            user_id = await unit_of_work.identity.authenticated_user_id(
                token_digest=digest, now=now
            )
            await unit_of_work.users.active(user_id)
            await unit_of_work.profiles.update_preferences(
                user_id=user_id,
                expected_version=expected_version,
                changes=changes,
                now=now,
            )
            return await current_learner_for_user(unit_of_work, user_id)
