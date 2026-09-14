from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.config import Config
from bot.db.repo import users as users_repo


class UserContextMiddleware(BaseMiddleware):
    def __init__(self, config: Config) -> None:
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id: int | None = None
        if isinstance(event, Update):
            if event.message is not None and event.message.from_user is not None:
                telegram_id = event.message.from_user.id
            elif event.callback_query is not None:
                telegram_id = event.callback_query.from_user.id

        current_user = None
        if telegram_id is not None:
            current_user = await users_repo.get_by_telegram_id(data["session"], telegram_id)

        # Admin rights require a profile: admin handlers rely on current_user (e.g. reviewer id).
        registered = current_user is not None
        data["current_user"] = current_user
        data["is_super_admin"] = registered and telegram_id == self.config.super_admin_id
        data["is_admin"] = data["is_super_admin"] or (registered and current_user.role == "admin")

        return await handler(event, data)
