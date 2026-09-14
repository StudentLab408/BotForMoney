from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.services.docx_export import DocRow, build_supplement_docx
from bot.utils.texts import EXPORT_CAPTION_INTERNAL, EXPORT_CAPTION_OFFICIAL
from bot.utils.time import month_name

VARIANTS = [
    (True, "official", EXPORT_CAPTION_OFFICIAL),
    (False, "internal", EXPORT_CAPTION_INTERNAL),
]


async def send_monthly_lists(
    bot: Bot, chat_id: int, year: int, month: int, rows: list[DocRow], *, caption_prefix: str = ""
) -> None:
    """Send the official and internal .docx lists for a month (rows must not be empty)."""
    for official, suffix, caption in VARIANTS:
        buf = build_supplement_docx(year, month, rows, official=official)
        await bot.send_document(
            chat_id,
            BufferedInputFile(buf.getvalue(), filename=f"nadbavki_{year}_{month:02d}_{suffix}.docx"),
            caption=caption_prefix + caption.format(month_name=month_name(month), year=year),
        )
