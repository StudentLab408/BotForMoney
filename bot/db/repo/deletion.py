"""Hard deletion, only after an explicit admin confirmation. Each function runs as one transaction."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Event, FsmRecord, Project, ProjectMember, Supplement, SupplementNotification, User


@dataclass
class DeletionImpact:
    supplements: int = 0
    approved: int = 0
    pending_ids: tuple[int, ...] = ()
    memberships: int = 0


async def _supplement_impact(session: AsyncSession, condition) -> DeletionImpact:
    rows = (await session.execute(select(Supplement.id, Supplement.status).where(condition))).all()
    return DeletionImpact(
        supplements=len(rows),
        approved=sum(1 for _, status in rows if status == "approved"),
        pending_ids=tuple(supplement_id for supplement_id, status in rows if status == "pending"),
    )


async def _count(session: AsyncSession, condition) -> int:
    return (await session.execute(select(func.count()).select_from(ProjectMember).where(condition))).scalar_one()


async def user_impact(session: AsyncSession, user: User) -> DeletionImpact:
    impact = await _supplement_impact(session, Supplement.student_id == user.id)
    impact.memberships = await _count(session, ProjectMember.user_id == user.id)
    return impact


async def project_impact(session: AsyncSession, project: Project) -> DeletionImpact:
    return DeletionImpact(memberships=await _count(session, ProjectMember.project_id == project.id))


async def event_impact(session: AsyncSession, event: Event) -> DeletionImpact:
    return await _supplement_impact(session, Supplement.event_id == event.id)


async def _delete_supplements(session: AsyncSession, condition) -> None:
    ids = select(Supplement.id).where(condition)
    await session.execute(delete(SupplementNotification).where(SupplementNotification.supplement_id.in_(ids)))
    await session.execute(delete(Supplement).where(condition))


async def delete_user(session: AsyncSession, user: User) -> None:
    """Delete a user with their requests, awards and project memberships.

    Where they acted as an admin for others, the records stay: the reference becomes NULL,
    while reviewed_by_name / cancelled_by_name keep who decided.
    """
    await _delete_supplements(session, Supplement.student_id == user.id)
    await session.execute(delete(ProjectMember).where(ProjectMember.user_id == user.id))

    for column in (Supplement.submitted_by, Supplement.reviewed_by, Supplement.cancelled_by):
        await session.execute(update(Supplement).where(column == user.id).values({column.key: None}))
    for column in (ProjectMember.added_by, ProjectMember.removed_by):
        await session.execute(update(ProjectMember).where(column == user.id).values({column.key: None}))
    await session.execute(update(Project).where(Project.created_by == user.id).values(created_by=None))
    await session.execute(update(Event).where(Event.created_by == user.id).values(created_by=None))

    # Private chat: chat_id == user_id, so the storage key contains ":<id>:<id>:".
    marker = f"%:{user.telegram_id}:{user.telegram_id}:%"
    await session.execute(delete(FsmRecord).where(FsmRecord.key.like(marker)))

    await session.delete(user)
    await session.commit()


async def delete_project(session: AsyncSession, project: Project) -> None:
    await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project.id))
    await session.delete(project)
    await session.commit()


async def delete_event(session: AsyncSession, event: Event) -> None:
    await _delete_supplements(session, Supplement.event_id == event.id)
    await session.delete(event)
    await session.commit()
