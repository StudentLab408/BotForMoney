"""Telegram "/" command lists: everyone sees the base list, admins additionally see admin commands."""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.repo import users as users_repo

logger = logging.getLogger(__name__)

BASE_COMMANDS = [
    ("start", "Регистрация / главное меню"),
    ("menu", "Быстрый переход в главное меню"),
    ("help", "Справка"),
]

ADMIN_COMMANDS = [
    ("admin", "Админ-панель"),
    ("requests", "Заявки на рассмотрении"),
    ("students", "Студенты"),
    ("projects", "Проекты"),
    ("events", "Конференции и мероприятия"),
    ("report", "Отчёт за месяц"),
    ("export", "Сформировать списки"),
]

SUPER_ADMIN_COMMANDS = [
    ("admins", "Администраторы"),
]


def _to_bot_commands(pairs: list[tuple[str, str]]) -> list[BotCommand]:
    return [BotCommand(command=command, description=description) for command, description in pairs]


async def set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(_to_bot_commands(BASE_COMMANDS))


async def set_admin_commands(bot: Bot, telegram_id: int, *, is_super_admin: bool) -> None:
    # A chat-scoped list replaces the default one for that chat, so it must repeat the base commands.
    pairs = BASE_COMMANDS + ADMIN_COMMANDS + (SUPER_ADMIN_COMMANDS if is_super_admin else [])
    try:
        await bot.set_my_commands(_to_bot_commands(pairs), scope=BotCommandScopeChat(chat_id=telegram_id))
    except TelegramAPIError:
        logger.warning("Could not set admin commands for %s", telegram_id)


async def reset_commands(bot: Bot, telegram_id: int) -> None:
    try:
        await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=telegram_id))
    except TelegramAPIError:
        logger.warning("Could not reset commands for %s", telegram_id)


async def sync_role_commands(bot: Bot, telegram_id: int, *, is_admin: bool, config: Config) -> None:
    if is_admin:
        await set_admin_commands(bot, telegram_id, is_super_admin=telegram_id == config.super_admin_id)
    else:
        await reset_commands(bot, telegram_id)


async def sync_all_admin_commands(bot: Bot, session: AsyncSession, config: Config) -> None:
    for telegram_id in await users_repo.list_admin_telegram_ids(session, config.super_admin_id):
        await set_admin_commands(bot, telegram_id, is_super_admin=telegram_id == config.super_admin_id)
