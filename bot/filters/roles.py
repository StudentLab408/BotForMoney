from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.db.models import User


class IsRegistered(BaseFilter):
    async def __call__(self, event: TelegramObject, current_user: User | None = None, **kwargs: Any) -> bool:
        return current_user is not None


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, is_admin: bool = False, **kwargs: Any) -> bool:
        return is_admin


class IsSuperAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, is_super_admin: bool = False, **kwargs: Any) -> bool:
        return is_super_admin
