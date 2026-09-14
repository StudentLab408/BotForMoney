from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User


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
    result = await session.execute(
        select(User).where(User.last_name.ilike(f"%{query}%")).limit(limit)
    )
    return list(result.scalars().all())


async def list_admins(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "admin"))
    return list(result.scalars().all())


async def list_students(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "student"))
    return list(result.scalars().all())


async def list_admin_telegram_ids(session: AsyncSession, super_admin_id: int) -> set[int]:
    admins = await list_admins(session)
    return {a.telegram_id for a in admins} | {super_admin_id}


async def set_role(session: AsyncSession, user_id: int, role: str) -> None:
    user = await session.get(User, user_id)
    if user is not None:
        user.role = role
        await session.commit()
