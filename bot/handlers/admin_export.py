from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.filters.roles import IsAdmin
from bot.keyboards.admin import month_picker_keyboard
from bot.services.docx_export import build_supplement_docx
from bot.services.reporting import build_doc_rows
from bot.states.report_month import ReportMonth
from bot.utils.texts import ASK_CUSTOM_MONTH, EXPORT_CAPTION, EXPORT_CHOOSE_MONTH, EXPORT_EMPTY
from bot.utils.time import current_period, month_name_nominative, previous_period

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def send_export_for_month(
    bot: Bot, session: AsyncSession, config: Config, chat_id: int, year: int, month: int
) -> None:
    rows = await build_doc_rows(session, config, year, month)
    month_name = month_name_nominative(month)
    if not rows:
        await bot.send_message(chat_id, EXPORT_EMPTY.format(month_name=month_name, year=year))
        return

    buf = build_supplement_docx(year, month, rows)
    filename = f"nadbavki_{year}_{month:02d}.docx"
    document = BufferedInputFile(buf.read(), filename=filename)
    await bot.send_document(
        chat_id, document, caption=EXPORT_CAPTION.format(month_name=month_name, year=year)
    )


@router.callback_query(F.data == "admin:export")
async def cb_export_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(EXPORT_CHOOSE_MONTH, reply_markup=month_picker_keyboard("export"))
    await callback.answer()


@router.callback_query(F.data == "month:export:current")
async def cb_export_current(callback: CallbackQuery, session: AsyncSession, config: Config, bot: Bot) -> None:
    year, month = current_period(config.timezone)
    await send_export_for_month(bot, session, config, callback.message.chat.id, year, month)
    await callback.answer()


@router.callback_query(F.data == "month:export:previous")
async def cb_export_previous(callback: CallbackQuery, session: AsyncSession, config: Config, bot: Bot) -> None:
    year, month = previous_period(*current_period(config.timezone))
    await send_export_for_month(bot, session, config, callback.message.chat.id, year, month)
    await callback.answer()


@router.callback_query(F.data == "month:export:custom")
async def cb_export_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReportMonth.waiting_custom_month)
    await state.update_data(purpose="export")
    await callback.message.edit_text(ASK_CUSTOM_MONTH)
    await callback.answer()
