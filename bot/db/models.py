import datetime as dt
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str] = mapped_column(String(100))
    group_number: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), default="student")  # 'student' | 'admin'

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()


class Supplement(Base):
    __tablename__ = "supplements"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    type: Mapped[str] = mapped_column(String(20))  # 'project' | 'conference' | 'event'
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 'pending'|'approved'|'rejected'

    period_year: Mapped[int] = mapped_column(index=True)
    period_month: Mapped[int] = mapped_column(index=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    project_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    regalia: Mapped[str | None] = mapped_column(Text, nullable=True)
    conference_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_did: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    student: Mapped["User"] = relationship(foreign_keys=[student_id])

    __table_args__ = (
        Index("ix_supplements_student_period_status", "student_id", "period_year", "period_month", "status"),
    )


class SupplementNotification(Base):
    __tablename__ = "supplement_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"), index=True)
    admin_telegram_id: Mapped[int] = mapped_column()
    chat_id: Mapped[int] = mapped_column()
    message_id: Mapped[int] = mapped_column()

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
