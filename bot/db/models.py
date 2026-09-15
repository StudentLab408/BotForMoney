"""Database schema. Nothing is ever hard-deleted: records change status or get archived instead."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, false, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str] = mapped_column(String(100))
    group_number: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | admin
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), index=True)
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()

    @property
    def short_name(self) -> str:
        return f"{self.last_name} {self.first_name[:1]}.".strip()


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    regalia: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ProjectMember(Base):
    """Project participation. Paid for every period p with start_period <= p < end_period."""

    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_period: Mapped[int] = mapped_column()
    # The month of removal is not paid, so end_period is exclusive; NULL means still a member.
    end_period: Mapped[int | None] = mapped_column()
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    removed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    removed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    project: Mapped[Project] = relationship(lazy="joined")
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")

    # A student can be a current member of a project only once.
    __table_args__ = (
        Index(
            "uq_project_members_current", "project_id", "user_id", unique=True, sqlite_where=text("end_period IS NULL")
        ),
    )


class Event(TimestampMixin, Base):
    """Catalog of conferences and events. Student-added entries stay hidden until a request with them is approved."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # conference | event
    name: Mapped[str] = mapped_column(String(300))
    held_on: Mapped[dt.date] = mapped_column(Date)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Supplement(TimestampMixin, Base):
    """A conference/event request or award. Project payments are derived from project_members instead."""

    __tablename__ = "supplements"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    project_name: Mapped[str | None] = mapped_column(Text)  # conference: project that was presented
    what_did: Mapped[str | None] = mapped_column(Text)  # event: what the student did

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending | approved | rejected | withdrawn | cancelled
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    period: Mapped[int | None] = mapped_column(index=True)  # month of approval

    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    withdrawn_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    event: Mapped[Event] = relationship(lazy="joined")
    student: Mapped[User] = relationship(foreign_keys=[student_id], lazy="joined")

    __table_args__ = (
        Index("ix_supplements_status_period", "status", "period"),
        # At most one open (pending or approved) request per student and event: no double payment.
        Index(
            "uq_supplements_open_per_event",
            "student_id",
            "event_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'approved')"),
        ),
    )


class SupplementNotification(Base):
    """An admin's copy of a request card, so every copy can be updated once someone decides."""

    __tablename__ = "supplement_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"), index=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class FsmRecord(Base):
    """aiogram FSM state and data, so unfinished forms survive a restart."""

    __tablename__ = "fsm_records"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(255))
    data: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
