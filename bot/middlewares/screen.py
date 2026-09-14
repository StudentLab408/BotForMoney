from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from bot.utils.screen import adopt_screen


class ScreenAdoptionMiddleware(BaseMiddleware):
    """Before a menu callback runs, treat the pressed message as the chat's screen.

    Register only on routers whose buttons live on screens (not on approval cards).
    """

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        if isinstance(event.message, Message) and state is not None:
            await adopt_screen(state, data["bot"], event.message.chat.id, event.message.message_id)
        return await handler(event, data)
