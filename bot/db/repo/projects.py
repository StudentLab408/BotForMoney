import datetime as dt

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Project, ProjectMember


async def get(session: AsyncSession, project_id: int) -> Project | None:
    return await session.get(Project, project_id)


async def list_all(session: AsyncSession, *, include_archived: bool = True) -> list[Project]:
    query = select(Project).order_by(Project.is_archived, Project.name)
    if not include_archived:
        query = query.where(Project.is_archived.is_(False))
    return list((await session.execute(query)).scalars().all())


async def create(session: AsyncSession, name: str, regalia: str | None, created_by: int) -> Project:
    project = Project(name=name, regalia=regalia, created_by=created_by)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update_fields(session: AsyncSession, project: Project, **fields: object) -> None:
    for name, value in fields.items():
        setattr(project, name, value)
    await session.commit()


def _active_in(period: int):
    return (ProjectMember.start_period <= period) & (
        or_(ProjectMember.end_period.is_(None), ProjectMember.end_period > period)
    )


async def get_member(session: AsyncSession, member_id: int) -> ProjectMember | None:
    return await session.get(ProjectMember, member_id)


async def list_members(session: AsyncSession, project_id: int, *, current_only: bool) -> list[ProjectMember]:
    query = select(ProjectMember).where(ProjectMember.project_id == project_id)
    if current_only:
        query = query.where(ProjectMember.end_period.is_(None))
    return list((await session.execute(query.order_by(ProjectMember.start_period))).scalars().all())


async def list_user_memberships(session: AsyncSession, user_id: int) -> list[ProjectMember]:
    result = await session.execute(
        select(ProjectMember)
        .where(ProjectMember.user_id == user_id)
        .order_by(ProjectMember.end_period.is_not(None), ProjectMember.start_period.desc())
    )
    return list(result.scalars().all())


async def list_current_memberships(session: AsyncSession) -> list[ProjectMember]:
    result = await session.execute(select(ProjectMember).where(ProjectMember.end_period.is_(None)))
    return list(result.scalars().all())


async def list_paid_memberships(session: AsyncSession, period: int) -> list[ProjectMember]:
    """Memberships that earn the project supplement in the given month."""
    result = await session.execute(select(ProjectMember).where(_active_in(period)))
    return list(result.scalars().all())


async def list_member_user_ids_ever(session: AsyncSession) -> set[int]:
    return set((await session.execute(select(ProjectMember.user_id).distinct())).scalars().all())


async def add_member(
    session: AsyncSession, project_id: int, user_id: int, period: int, added_by: int
) -> ProjectMember | None:
    """Add a current member. Returns None if the user is already a current member of this project."""
    existing = await session.execute(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.end_period.is_(None),
        )
    )
    if existing.first() is not None:
        return None
    member = ProjectMember(project_id=project_id, user_id=user_id, start_period=period, added_by=added_by)
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:  # another admin added them at the same moment
        await session.rollback()
        return None
    return await get_member(session, member.id)


async def end_membership(session: AsyncSession, member: ProjectMember, period: int, removed_by: int) -> bool:
    """End from the given month on (that month is no longer paid). False if it had already ended."""
    result = await session.execute(
        update(ProjectMember)
        .where(ProjectMember.id == member.id, ProjectMember.end_period.is_(None))
        .values(end_period=max(period, member.start_period), removed_by=removed_by, removed_at=dt.datetime.now(dt.UTC))
    )
    await session.commit()
    await session.refresh(member)
    return result.rowcount > 0


async def end_all_for_user(session: AsyncSession, user_id: int, period: int, removed_by: int) -> None:
    for member in await list_user_memberships(session, user_id):
        if member.end_period is None:
            await end_membership(session, member, period, removed_by)
