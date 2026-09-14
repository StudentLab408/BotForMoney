import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import Config
from bot.db.engine import session_scope
from bot.db.repo import users as users_repo
from bot.services.docx_export import build_supplement_docx
from bot.services.reporting import build_doc_rows
from bot.utils.texts import AUTO_EXPORT_CAPTION, EXPORT_EMPTY
from bot.utils.time import current_period, month_name_nominative, previous_period

logger = logging.getLogger(__name__)


async def _auto_send_monthly_list(bot: Bot, config: Config) -> None:
    year, month = previous_period(*current_period(config.timezone))
    month_name = month_name_nominative(month)

    async with session_scope() as session:
        rows = await build_doc_rows(session, config, year, month)
        admin_ids = await users_repo.list_admin_telegram_ids(session, config.super_admin_id)

    file_bytes = build_supplement_docx(year, month, rows).read() if rows else None

    for admin_id in admin_ids:
        try:
            if file_bytes is None:
                await bot.send_message(admin_id, EXPORT_EMPTY.format(month_name=month_name, year=year))
            else:
                document = BufferedInputFile(file_bytes, filename=f"nadbavki_{year}_{month:02d}.docx")
                await bot.send_document(
                    admin_id, document, caption=AUTO_EXPORT_CAPTION.format(month_name=month_name, year=year)
                )
        except Exception:
            logger.exception("Failed to send auto monthly list to admin %s", admin_id)


def setup_scheduler(bot: Bot, config: Config) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        _auto_send_monthly_list,
        trigger=CronTrigger(day=config.auto_send_day, hour=config.auto_send_hour, minute=0),
        args=[bot, config],
    )
    scheduler.start()
    return scheduler
