import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User


async def get(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_or_update(
    session: AsyncSession,
    telegram_id: int,
    last_name: str,
    first_name: str,
    middle_name: str,
    group_number: str,
) -> User:
    user = await get_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, role="student")
        session.add(user)
    user.last_name = last_name
    user.first_name = first_name
    user.middle_name = middle_name
    user.group_number = group_number
    await session.commit()
    await session.refresh(user)
    return user


async def list_all(session: AsyncSession, *, archived: bool = False) -> list[User]:
    result = await session.execute(
        select(User).where(User.is_archived == archived).order_by(User.last_name, User.first_name)
    )
    return list(result.scalars().all())


def search(users: list[User], query: str) -> list[User]:
    # Filtered in Python: SQLite LIKE is case-insensitive only for ASCII, so Cyrillic wouldn't match.
    needle = query.casefold()
    return [u for u in users if needle in u.full_name.casefold() or needle in u.group_number.casefold()]


async def list_groups(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(User.group_number).where(User.is_archived.is_(False)).distinct().order_by(User.group_number)
    )
    return list(result.scalars().all())


async def list_admins(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "admin").order_by(User.last_name))
    return list(result.scalars().all())


async def list_admin_telegram_ids(session: AsyncSession, super_admin_id: int) -> set[int]:
    """Active admins plus the super-admin (only once they have registered)."""
    result = await session.execute(
        select(User.telegram_id).where(
            or_(User.role == "admin", User.telegram_id == super_admin_id), User.is_archived.is_(False)
        )
    )
    return set(result.scalars().all())


async def set_role(session: AsyncSession, user: User, role: str) -> None:
    user.role = role
    await session.commit()


async def set_archived(session: AsyncSession, user: User, archived: bool) -> None:
    user.is_archived = archived
    user.archived_at = dt.datetime.now(dt.UTC) if archived else None
    if archived:
        user.role = "student"
    await session.commit()
