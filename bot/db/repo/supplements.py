import datetime as dt
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Supplement, SupplementNotification


async def create_project(
    session: AsyncSession,
    student_id: int,
    admin_id: int,
    project_name: str,
    regalia: str,
    amount: Decimal,
    period_year: int,
    period_month: int,
) -> Supplement:
    supplement = Supplement(
        student_id=student_id,
        type="project",
        status="approved",
        period_year=period_year,
        period_month=period_month,
        amount=amount,
        project_name=project_name,
        regalia=regalia,
        submitted_by=admin_id,
        reviewed_by=admin_id,
        reviewed_at=dt.datetime.now(dt.UTC),
    )
    session.add(supplement)
    await session.commit()
    await session.refresh(supplement)
    return supplement


async def create_conference(
    session: AsyncSession,
    student_id: int,
    conference_name: str,
    project_name: str,
    period_year: int,
    period_month: int,
) -> Supplement:
    supplement = Supplement(
        student_id=student_id,
        type="conference",
        status="pending",
        period_year=period_year,
        period_month=period_month,
        amount=None,
        conference_name=conference_name,
        project_name=project_name,
        submitted_by=student_id,
    )
    session.add(supplement)
    await session.commit()
    await session.refresh(supplement)
    return supplement


async def create_event(
    session: AsyncSession,
    student_id: int,
    event_name: str,
    what_did: str,
    period_year: int,
    period_month: int,
) -> Supplement:
    supplement = Supplement(
        student_id=student_id,
        type="event",
        status="pending",
        period_year=period_year,
        period_month=period_month,
        amount=None,
        event_name=event_name,
        what_did=what_did,
        submitted_by=student_id,
    )
    session.add(supplement)
    await session.commit()
    await session.refresh(supplement)
    return supplement


async def get(session: AsyncSession, supplement_id: int) -> Supplement | None:
    return await session.get(Supplement, supplement_id)


async def approve(
    session: AsyncSession, supplement_id: int, amount: Decimal, admin_id: int
) -> bool:
    """Atomically approve a pending supplement, setting its amount. Returns False if already handled."""
    result = await session.execute(
        update(Supplement)
        .where(Supplement.id == supplement_id, Supplement.status == "pending")
        .values(
            status="approved",
            amount=amount,
            reviewed_by=admin_id,
            reviewed_at=dt.datetime.now(dt.UTC),
        )
    )
    await session.commit()
    return result.rowcount > 0


async def reject(
    session: AsyncSession, supplement_id: int, admin_id: int, reason: str | None
) -> bool:
    result = await session.execute(
        update(Supplement)
        .where(Supplement.id == supplement_id, Supplement.status == "pending")
        .values(
            status="rejected",
            reviewed_by=admin_id,
            reviewed_at=dt.datetime.now(dt.UTC),
            reject_reason=reason,
        )
    )
    await session.commit()
    return result.rowcount > 0


async def list_for_student_month(
    session: AsyncSession, student_id: int, period_year: int, period_month: int
) -> list[Supplement]:
    result = await session.execute(
        select(Supplement).where(
            Supplement.student_id == student_id,
            Supplement.period_year == period_year,
            Supplement.period_month == period_month,
        )
    )
    return list(result.scalars().all())


async def list_students_with_activity(
    session: AsyncSession, period_year: int, period_month: int
) -> list[int]:
    result = await session.execute(
        select(Supplement.student_id)
        .where(
            Supplement.period_year == period_year,
            Supplement.period_month == period_month,
            Supplement.status == "approved",
        )
        .distinct()
    )
    return [row[0] for row in result.all()]


async def list_student_activity_types(session: AsyncSession) -> dict[int, set[str]]:
    """All-time map of student_id -> set of supplement types ever submitted (any status)."""
    result = await session.execute(select(Supplement.student_id, Supplement.type).distinct())
    activity: dict[int, set[str]] = {}
    for student_id, type_ in result.all():
        activity.setdefault(student_id, set()).add(type_)
    return activity


async def add_notification(
    session: AsyncSession, supplement_id: int, admin_telegram_id: int, chat_id: int, message_id: int
) -> None:
    session.add(
        SupplementNotification(
            supplement_id=supplement_id,
            admin_telegram_id=admin_telegram_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    )
    await session.commit()


async def list_notifications(session: AsyncSession, supplement_id: int) -> list[SupplementNotification]:
    result = await session.execute(
        select(SupplementNotification).where(SupplementNotification.supplement_id == supplement_id)
    )
    return list(result.scalars().all())
