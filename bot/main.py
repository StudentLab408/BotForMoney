import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.types import BotCommand

from bot.config import Config, load_config
from bot.db.engine import dispose_engine, init_models
from bot.handlers import (
    admin_approval,
    admin_management,
    admin_panel,
    admin_project_entry,
    admin_reports,
    common,
    fallback,
    registration,
    student_cabinet,
)
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.screen import ScreenAdoptionMiddleware
from bot.middlewares.user_context import UserContextMiddleware
from bot.services.scheduler import setup_scheduler

# Order matters: the first router whose filters match handles the update; fallback must stay last.
ROUTERS = [
    common.router,
    registration.router,
    student_cabinet.router,
    admin_panel.router,
    admin_approval.router,
    admin_project_entry.router,
    admin_management.router,
    admin_reports.router,
    fallback.router,
]

# Routers whose buttons sit on the chat's "screen" message (approval cards and fallback are excluded).
SCREEN_ROUTERS = [
    common.router,
    registration.router,
    student_cabinet.router,
    admin_panel.router,
    admin_project_entry.router,
    admin_management.router,
    admin_reports.router,
]


def create_dispatcher(config: Config) -> Dispatcher:
    """Build the dispatcher. Routers are module-level singletons, so call this once per process."""
    dp = Dispatcher()
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
    await init_models(config.db_path)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(config)
    scheduler = setup_scheduler(bot, config)
    await bot.set_my_commands([BotCommand(command=cmd, description=desc) for cmd, desc in common.BOT_COMMANDS])
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
