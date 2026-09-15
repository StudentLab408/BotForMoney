"""Conference/event requests and awards. Status changes are conditional updates, so two admins can't both act."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Supplement, SupplementNotification

OPEN_STATUSES = ("pending", "approved")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def get(session: AsyncSession, supplement_id: int) -> Supplement | None:
    return await session.get(Supplement, supplement_id, populate_existing=True)


async def has_open_request(session: AsyncSession, student_id: int, event_id: int) -> bool:
    result = await session.execute(
        select(Supplement.id).where(
            Supplement.student_id == student_id,
            Supplement.event_id == event_id,
            Supplement.status.in_(OPEN_STATUSES),
        )
    )
    return result.first() is not None


async def _insert_open(session: AsyncSession, supplement: Supplement) -> Supplement | None:
    """Insert an open request/award. None if the student already has an open one for this event."""
    session.add(supplement)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return None
    return await get(session, supplement.id)


async def create_request(
    session: AsyncSession,
    student_id: int,
    event_id: int,
    *,
    project_name: str | None,
    what_did: str | None,
) -> Supplement | None:
    supplement = Supplement(
        student_id=student_id,
        event_id=event_id,
        project_name=project_name,
        what_did=what_did,
        status="pending",
        submitted_by=student_id,
    )
    return await _insert_open(session, supplement)


async def create_award(
    session: AsyncSession,
    student_id: int,
    event_id: int,
    *,
    project_name: str | None,
    what_did: str | None,
    amount: Decimal,
    period: int,
    admin_id: int,
    admin_name: str,
) -> Supplement | None:
    """An award added by an admin directly — approved at once."""
    supplement = Supplement(
        student_id=student_id,
        event_id=event_id,
        project_name=project_name,
        what_did=what_did,
        status="approved",
        amount=amount,
        period=period,
        submitted_by=admin_id,
        reviewed_by=admin_id,
        reviewed_by_name=admin_name,
        reviewed_at=_now(),
    )
    return await _insert_open(session, supplement)


async def _transition(session: AsyncSession, supplement_id: int, from_status: str, **values: object) -> bool:
    result = await session.execute(
        update(Supplement).where(Supplement.id == supplement_id, Supplement.status == from_status).values(**values)
    )
    await session.commit()
    return result.rowcount > 0


async def approve(
    session: AsyncSession, supplement_id: int, amount: Decimal, period: int, admin_id: int, admin_name: str
) -> bool:
    return await _transition(
        session,
        supplement_id,
        "pending",
        status="approved",
        amount=amount,
        period=period,
        reviewed_by=admin_id,
        reviewed_by_name=admin_name,
        reviewed_at=_now(),
    )


async def reject(session: AsyncSession, supplement_id: int, admin_id: int, admin_name: str, reason: str | None) -> bool:
    return await _transition(
        session,
        supplement_id,
        "pending",
        status="rejected",
        reviewed_by=admin_id,
        reviewed_by_name=admin_name,
        reviewed_at=_now(),
        reject_reason=reason,
    )


async def withdraw(session: AsyncSession, supplement_id: int) -> bool:
    return await _transition(session, supplement_id, "pending", status="withdrawn", withdrawn_at=_now())


async def cancel(session: AsyncSession, supplement_id: int, admin_id: int, admin_name: str, reason: str | None) -> bool:
    return await _transition(
        session,
        supplement_id,
        "approved",
        status="cancelled",
        cancelled_by=admin_id,
        cancelled_by_name=admin_name,
        cancelled_at=_now(),
        cancel_reason=reason,
    )


async def change_amount(session: AsyncSession, supplement_id: int, amount: Decimal) -> bool:
    return await _transition(session, supplement_id, "approved", amount=amount)


async def list_pending(session: AsyncSession) -> list[Supplement]:
    result = await session.execute(
        select(Supplement).where(Supplement.status == "pending").order_by(Supplement.created_at, Supplement.id)
    )
    return list(result.scalars().all())


async def count_pending(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).where(Supplement.status == "pending"))).scalar_one()


async def list_pending_for_student(session: AsyncSession, student_id: int) -> list[Supplement]:
    result = await session.execute(
        select(Supplement).where(Supplement.student_id == student_id, Supplement.status == "pending")
    )
    return list(result.scalars().all())


async def list_approved_for_period(session: AsyncSession, period: int) -> list[Supplement]:
    result = await session.execute(
        select(Supplement).where(Supplement.status == "approved", Supplement.period == period)
    )
    return list(result.scalars().all())


async def list_for_student(session: AsyncSession, student_id: int) -> list[Supplement]:
    result = await session.execute(
        select(Supplement)
        .where(Supplement.student_id == student_id)
        .order_by(Supplement.created_at.desc(), Supplement.id.desc())
    )
    return list(result.scalars().all())


async def list_for_event(session: AsyncSession, event_id: int) -> list[Supplement]:
    result = await session.execute(
        select(Supplement)
        .where(Supplement.event_id == event_id, Supplement.status == "approved")
        .order_by(Supplement.period)
    )
    return list(result.scalars().all())


async def status_counts_by_student(session: AsyncSession) -> dict[int, dict[str, int]]:
    result = await session.execute(
        select(Supplement.student_id, Supplement.status, func.count()).group_by(
            Supplement.student_id, Supplement.status
        )
    )
    counts: dict[int, dict[str, int]] = {}
    for student_id, status, count in result.all():
        counts.setdefault(student_id, {})[status] = count
    return counts


async def add_notification(
    session: AsyncSession, supplement_id: int, admin_telegram_id: int, chat_id: int, message_id: int
) -> None:
    session.add(
        SupplementNotification(
            supplement_id=supplement_id, admin_telegram_id=admin_telegram_id, chat_id=chat_id, message_id=message_id
        )
    )
    await session.commit()


async def list_notifications(session: AsyncSession, supplement_id: int) -> list[SupplementNotification]:
    result = await session.execute(
        select(SupplementNotification).where(SupplementNotification.supplement_id == supplement_id)
    )
    return list(result.scalars().all())
