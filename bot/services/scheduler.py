import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Config
from bot.db.engine import session_scope
from bot.db.repo import users as users_repo
from bot.services.backup import backup_database
from bot.services.list_delivery import send_monthly_lists
from bot.services.reporting import build_doc_rows
from bot.utils.texts import AUTO_EXPORT_PREFIX, BACKUP_CAPTION, EXPORT_EMPTY
from bot.utils.time import current_period, format_date, now, period_title

logger = logging.getLogger(__name__)


async def auto_send_monthly_lists(bot: Bot, config: Config) -> None:
    period = current_period(config.timezone) - 1

    async with session_scope() as session:
        rows = await build_doc_rows(session, config, period)
        admin_ids = await users_repo.list_admin_telegram_ids(session, config.super_admin_id)

    for admin_id in admin_ids:
        try:
            if rows:
                await send_monthly_lists(bot, admin_id, period, rows, caption_prefix=AUTO_EXPORT_PREFIX)
            else:
                empty = EXPORT_EMPTY.format(month_name=period_title(period))
                await bot.send_message(admin_id, AUTO_EXPORT_PREFIX + empty)
        except TelegramAPIError:
            logger.exception("Failed to send monthly lists to admin %s", admin_id)


async def run_backup(config: Config) -> None:
    today = now(config.timezone).date()
    path = await asyncio.to_thread(backup_database, config.db_path, config.backup_dir, today, config.backup_keep_days)
    logger.info("Database backup written to %s", path)


async def send_weekly_backup(bot: Bot, config: Config) -> None:
    today = now(config.timezone).date()
    path = await asyncio.to_thread(backup_database, config.db_path, config.backup_dir, today, config.backup_keep_days)
    try:
        await bot.send_document(
            config.super_admin_id, FSInputFile(path), caption=BACKUP_CAPTION.format(date=format_date(today))
        )
    except TelegramAPIError:
        logger.exception("Failed to send the weekly backup to the super-admin")


def setup_scheduler(bot: Bot, config: Config) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    job_options = {"misfire_grace_time": 3600, "coalesce": True}
    scheduler.add_job(
        auto_send_monthly_lists,
        CronTrigger(day=config.auto_send_day, hour=config.auto_send_hour, minute=0, timezone=config.timezone),
        args=[bot, config],
        **job_options,
    )
    scheduler.add_job(run_backup, CronTrigger(hour=3, minute=0, timezone=config.timezone), args=[config], **job_options)
    scheduler.add_job(
        send_weekly_backup,
        CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=config.timezone),
        args=[bot, config],
        **job_options,
    )
    scheduler.start()
    return scheduler
