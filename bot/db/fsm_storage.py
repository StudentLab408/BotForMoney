import json
from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from bot.db.engine import session_scope
from bot.db.models import FsmRecord


class DatabaseStorage(BaseStorage):
    """Keeps FSM state and data in the bot's database, so unfinished forms survive a restart."""

    @staticmethod
    def _key(key: StorageKey) -> str:
        parts = (key.bot_id, key.chat_id, key.user_id, key.thread_id, key.business_connection_id, key.destiny)
        return ":".join(str(part) for part in parts)

    async def _save(self, key: StorageKey, **values: Any) -> None:
        async with session_scope() as session:
            record = await session.get(FsmRecord, self._key(key))
            if record is None:
                record = FsmRecord(key=self._key(key), state=None, data="{}")
                session.add(record)
            for name, value in values.items():
                setattr(record, name, value)
            await session.commit()

    async def _load(self, key: StorageKey) -> FsmRecord | None:
        async with session_scope() as session:
            return await session.get(FsmRecord, self._key(key))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await self._save(key, state=state.state if isinstance(state, State) else state)

    async def get_state(self, key: StorageKey) -> str | None:
        record = await self._load(key)
        return record.state if record else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._save(key, data=json.dumps(dict(data), ensure_ascii=False))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        record = await self._load(key)
        return json.loads(record.data) if record else {}

    async def close(self) -> None:
        pass
