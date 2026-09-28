"""One PostgreSQL transaction shared by cooperating business modules."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction, async_sessionmaker

from mori.modules.access.persistence import SqlAlchemyAccessStore
from mori.modules.curriculum.persistence import SqlAlchemyCourseCatalogStore
from mori.modules.identity.persistence import SqlAlchemyIdentityStore
from mori.modules.learner_profiles.persistence import SqlAlchemyLearnerProfileStore
from mori.modules.user.persistence import SqlAlchemyUserStore


class SqlAlchemyUnitOfWork:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker
        self._session: AsyncSession | None = None
        self._transaction: AsyncSessionTransaction | None = None
        self._identity: SqlAlchemyIdentityStore | None = None
        self._user: SqlAlchemyUserStore | None = None
        self._profiles: SqlAlchemyLearnerProfileStore | None = None
        self._curriculum: SqlAlchemyCourseCatalogStore | None = None
        self._access: SqlAlchemyAccessStore | None = None

    @property
    def identity(self) -> SqlAlchemyIdentityStore:
        if self._identity is None:
            raise RuntimeError("unit of work has not been entered")
        return self._identity

    @property
    def user(self) -> SqlAlchemyUserStore:
        if self._user is None:
            raise RuntimeError("unit of work has not been entered")
        return self._user

    @property
    def profiles(self) -> SqlAlchemyLearnerProfileStore:
        if self._profiles is None:
            raise RuntimeError("unit of work has not been entered")
        return self._profiles

    @property
    def curriculum(self) -> SqlAlchemyCourseCatalogStore:
        if self._curriculum is None:
            raise RuntimeError("unit of work has not been entered")
        return self._curriculum

    @property
    def access(self) -> SqlAlchemyAccessStore:
        if self._access is None:
            raise RuntimeError("unit of work has not been entered")
        return self._access

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_maker()
        self._transaction = await self._session.begin()
        self._identity = SqlAlchemyIdentityStore(self._session)
        self._user = SqlAlchemyUserStore(self._session)
        self._profiles = SqlAlchemyLearnerProfileStore(self._session)
        self._curriculum = SqlAlchemyCourseCatalogStore(self._session)
        self._access = SqlAlchemyAccessStore(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._transaction is None or self._session is None:
            return
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self._session.close()


class SqlAlchemyUnitOfWorkFactory:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_maker)
