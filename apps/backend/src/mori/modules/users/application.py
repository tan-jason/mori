"""User queries, including the composed current learner view."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from mori.modules.identity.application import IdentityService
from mori.modules.users.domain import CurrentLearner
from mori.persistence.ports import UnitOfWork, UnitOfWorkFactory


async def current_learner_for_user(unit_of_work: UnitOfWork, user_id: UUID) -> CurrentLearner:
    user = await unit_of_work.users.active(user_id)
    profile, preferences = await unit_of_work.profiles.current(user_id)
    return CurrentLearner(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        onboarding_complete=user.onboarding_completed_at is not None and profile is not None,
        version=user.version,
        language_profile=profile,
        preferences=preferences,
    )


class UserService:
    def __init__(
        self, *, unit_of_work_factory: UnitOfWorkFactory, identity: IdentityService
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._identity = identity

    async def current_learner(self, *, session_token: str) -> CurrentLearner:
        digest = self._identity.session_digest(session_token)
        async with self._unit_of_work_factory() as unit_of_work:
            user_id = await unit_of_work.identity.authenticated_user_id(
                token_digest=digest, now=datetime.now(UTC)
            )
            return await current_learner_for_user(unit_of_work, user_id)
