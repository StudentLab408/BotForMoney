from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_many(session: AsyncSession, user_ids: list[int]) -> list[User]:
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return list(result.scalars().all())


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
        user = User(
            telegram_id=telegram_id,
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            group_number=group_number,
            role="student",
        )
        session.add(user)
    else:
        user.last_name = last_name
        user.first_name = first_name
        user.middle_name = middle_name
        user.group_number = group_number
    await session.commit()
    await session.refresh(user)
    return user


async def search_by_last_name(session: AsyncSession, query: str, limit: int = 10) -> list[User]:
    # Filtered in Python: SQLite LIKE is case-insensitive only for ASCII, so Cyrillic wouldn't match.
    needle = query.casefold()
    result = await session.execute(select(User).order_by(User.last_name, User.first_name))
    return [u for u in result.scalars() if needle in u.last_name.casefold()][:limit]


async def list_admins(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "admin").order_by(User.last_name))
    return list(result.scalars().all())


async def list_students(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "student"))
    return list(result.scalars().all())


async def list_admin_telegram_ids(session: AsyncSession, super_admin_id: int) -> set[int]:
    """Registered admins plus the super-admin (only once they have registered)."""
    result = await session.execute(
        select(User.telegram_id).where(or_(User.role == "admin", User.telegram_id == super_admin_id))
    )
    return set(result.scalars().all())


async def set_role(session: AsyncSession, user_id: int, role: str) -> None:
    user = await session.get(User, user_id)
    if user is not None:
        user.role = role
        await session.commit()
