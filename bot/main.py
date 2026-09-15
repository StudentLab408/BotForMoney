import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.storage.base import BaseEventIsolation
from aiogram.fsm.storage.memory import SimpleEventIsolation

from bot.config import Config, load_config
from bot.db.engine import dispose_engine, init_database, session_scope
from bot.db.fsm_storage import DatabaseStorage
from bot.handlers import (
    admin_cards,
    admin_catalog,
    admin_commands,
    admin_management,
    admin_panel,
    admin_reports,
    admin_requests,
    admin_students,
    common,
    fallback,
    registration,
    student_cabinet,
)
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.screen import ScreenAdoptionMiddleware
from bot.middlewares.user_context import UserContextMiddleware
from bot.services.commands import set_default_commands, sync_all_admin_commands
from bot.services.scheduler import setup_scheduler

# Order matters: the first router whose filters match handles the update; fallback must stay last.
# Command routers come first so commands work even in the middle of a form.
ROUTERS = [
    common.router,
    admin_commands.router,
    registration.router,
    student_cabinet.router,
    admin_panel.router,
    admin_cards.router,
    admin_requests.router,
    admin_students.router,
    admin_catalog.router,
    admin_reports.router,
    admin_management.router,
    fallback.router,
]

# Routers whose buttons sit on the chat's "screen" message (pushed request cards and fallback are excluded).
SCREEN_ROUTERS = [
    common.router,
    registration.router,
    student_cabinet.router,
    admin_panel.router,
    admin_requests.router,
    admin_students.router,
    admin_catalog.router,
    admin_reports.router,
    admin_management.router,
]


def create_dispatcher(config: Config, events_isolation: BaseEventIsolation | None = None) -> Dispatcher:
    """Build the dispatcher. Routers are module-level singletons, so call this once per process."""
    # One update per user at a time: a double tap can't run a confirm step twice.
    dp = Dispatcher(storage=DatabaseStorage(), events_isolation=events_isolation or SimpleEventIsolation())
    dp["config"] = config

    dp.message.filter(F.chat.type == ChatType.PRIVATE)
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserContextMiddleware(config))

    screen_middleware = ScreenAdoptionMiddleware()
    for router in SCREEN_ROUTERS:
        router.callback_query.middleware(screen_middleware)
    dp.include_routers(*ROUTERS)
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    await init_database(config.db_path)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(config)
    scheduler = setup_scheduler(bot, config)
    await set_default_commands(bot)
    async with session_scope() as session:
        await sync_all_admin_commands(bot, session, config)
    # Keep updates sent while the bot was down: forms are persisted, so they can continue.
    await bot.delete_webhook(drop_pending_updates=False)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
