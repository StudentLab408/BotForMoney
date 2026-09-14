import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Config
from bot.db.engine import session_scope
from bot.db.repo import users as users_repo
from bot.services.list_delivery import send_monthly_lists
from bot.services.reporting import build_doc_rows
from bot.utils.texts import AUTO_EXPORT_PREFIX, EXPORT_EMPTY
from bot.utils.time import current_period, month_name, previous_period

logger = logging.getLogger(__name__)


async def auto_send_monthly_lists(bot: Bot, config: Config) -> None:
    year, month = previous_period(*current_period(config.timezone))

    async with session_scope() as session:
        rows = await build_doc_rows(session, config, year, month)
        admin_ids = await users_repo.list_admin_telegram_ids(session, config.super_admin_id)

    for admin_id in admin_ids:
        try:
            if rows:
                await send_monthly_lists(bot, admin_id, year, month, rows, caption_prefix=AUTO_EXPORT_PREFIX)
            else:
                empty = EXPORT_EMPTY.format(month_name=month_name(month), year=year)
                await bot.send_message(admin_id, AUTO_EXPORT_PREFIX + empty)
        except TelegramAPIError:
            logger.exception("Failed to send monthly lists to admin %s", admin_id)


def setup_scheduler(bot: Bot, config: Config) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        auto_send_monthly_lists,
        trigger=CronTrigger(day=config.auto_send_day, hour=config.auto_send_hour, minute=0, timezone=config.timezone),
        args=[bot, config],
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
