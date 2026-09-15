import datetime as dt

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Event, Supplement


async def get(session: AsyncSession, event_id: int) -> Event | None:
    return await session.get(Event, event_id)


async def list_for_kind(
    session: AsyncSession, kind: str, *, verified_only: bool, include_archived: bool = False
) -> list[Event]:
    query = select(Event).where(Event.kind == kind)
    if verified_only:
        query = query.where(Event.is_verified.is_(True))
    if not include_archived:
        query = query.where(Event.is_archived.is_(False))
    query = query.order_by(Event.is_archived, Event.held_on.desc(), Event.name)
    return list((await session.execute(query)).scalars().all())


def search(events: list[Event], query: str) -> list[Event]:
    needle = query.casefold()
    return [e for e in events if needle in e.name.casefold()]


async def create(
    session: AsyncSession, kind: str, name: str, held_on: dt.date, created_by: int, *, verified: bool
) -> Event:
    event = Event(kind=kind, name=name, held_on=held_on, created_by=created_by, is_verified=verified)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def update_fields(session: AsyncSession, event: Event, **fields: object) -> None:
    for name, value in fields.items():
        setattr(event, name, value)
    await session.commit()


async def merge(session: AsyncSession, source: Event, target: Event) -> None:
    """Move every request of a duplicate to the target entry and archive the duplicate."""
    await session.execute(update(Supplement).where(Supplement.event_id == source.id).values(event_id=target.id))
    source.is_archived = True
    await session.commit()
