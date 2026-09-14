import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.db.engine import init_models
from bot.handlers import (
    admin_approval,
    admin_export,
    admin_management,
    admin_panel,
    admin_project_entry,
    admin_reports,
    common,
    registration,
    student_cabinet,
)
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.user_context import UserContextMiddleware
from bot.services.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    await init_models(config.db_path)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["config"] = config

    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserContextMiddleware(config))

    dp.include_router(common.router)
    dp.include_router(registration.router)
    dp.include_router(student_cabinet.router)
    dp.include_router(admin_panel.router)
    dp.include_router(admin_approval.router)
    dp.include_router(admin_project_entry.router)
    dp.include_router(admin_management.router)
    dp.include_router(admin_reports.router)
    dp.include_router(admin_export.router)

    setup_scheduler(bot, config)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
