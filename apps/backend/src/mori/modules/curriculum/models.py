"""Published language pair catalog persistence entity."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mori.persistence.base import Base


class CourseCatalogModel(Base):
    __tablename__ = "course_catalog"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_course_catalog_status",
        ),
        CheckConstraint(
            "status != 'published' OR "
            "(active_curriculum_version IS NOT NULL AND pair_policy_version IS NOT NULL "
            "AND voice_policy_version IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_course_catalog_published_bundle",
        ),
        UniqueConstraint("base_language_id", "target_language_id", name="uq_course_catalog_pair"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    base_language_id: Mapped[str] = mapped_column(String(32), nullable=False)
    target_language_id: Mapped[str] = mapped_column(String(32), nullable=False)
    base_language_name: Mapped[str] = mapped_column(String(80), nullable=False)
    target_language_name: Mapped[str] = mapped_column(String(80), nullable=False)
    target_native_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_curriculum_version: Mapped[str | None] = mapped_column(String(64))
    pair_policy_version: Mapped[str | None] = mapped_column(String(64))
    voice_policy_version: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
