from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hh_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    area: Mapped[str | None] = mapped_column(String(256), nullable=True)
    salary_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(256), nullable=True)
    employment: Mapped[str | None] = mapped_column(String(256), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="new", index=True)
    raw_payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    has_test: Mapped[bool] = mapped_column(Boolean, default=False)
    response_letter_required: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    scores: Mapped[list["VacancyScore"]] = relationship(back_populates="vacancy")
    cover_letters: Mapped[list["CoverLetter"]] = relationship(back_populates="vacancy")
    applications: Mapped[list["Application"]] = relationship(back_populates="vacancy")


class VacancyScore(Base):
    __tablename__ = "vacancy_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    matched_skills_json: Mapped[str] = mapped_column(Text, default="[]")
    concerns_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    vacancy: Mapped[Vacancy] = relationship(back_populates="scores")


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(128))
    model: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_errors_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    vacancy: Mapped[Vacancy] = relationship(back_populates="cover_letters")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("vacancy_id", name="uq_applications_vacancy_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    decision_source: Mapped[str] = mapped_column(String(64), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vacancy: Mapped[Vacancy] = relationship(back_populates="applications")


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_blacklist_kind_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(512))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(32))
    event: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
