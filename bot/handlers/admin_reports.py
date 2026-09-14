from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.filters.roles import IsAdmin
from bot.handlers.admin_export import send_export_for_month
from bot.keyboards.admin import back_to_admin_menu_keyboard, month_picker_keyboard
from bot.services.reporting import MonthReport, StudentActivityReport, build_month_report, build_student_activity_report
from bot.states.report_month import ReportMonth
from bot.utils.texts import ASK_CUSTOM_MONTH, INVALID_MONTH_FORMAT, REPORT_CHOOSE_MONTH
from bot.utils.time import current_period, month_name_nominative, parse_month_string, previous_period

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _format_report(report: MonthReport) -> str:
    month_name = month_name_nominative(report.month)
    lines = [
        f"📊 <b>Отчёт за {month_name} {report.year}</b>",
        "",
        f"👥 Студентов с начислением: {report.student_count}",
        f"💰 Итого начислено (net): {report.total_net} BYN",
        f"🏦 Удержано в фонд лаборатории: {report.total_withheld} BYN",
        f"💵 Итого gross: {report.total_gross} BYN",
        "",
        f"📁 Проекты: {report.project_count} шт. — {report.project_gross} BYN",
        f"🏛 Конференции: {report.conference_count} шт. — {report.conference_gross} BYN",
        f"🎪 Мероприятия: {report.event_count} шт. — {report.event_gross} BYN",
    ]
    if report.students_capped:
        lines.append(f"\n⚠️ Студентов, у кого сумма урезана лимитом 200 BYN: {report.students_capped}")
    return "\n".join(lines)


def _format_activity(report: StudentActivityReport) -> str:
    def _names(users: list) -> str:
        if not users:
            return "— никого —"
        return "\n".join(f"• {u.last_name} {u.first_name} ({u.group_number})" for u in users)

    return (
        "👥 <b>Активность студентов</b> (за всё время)\n\n"
        f"📁 <b>Есть проектная надбавка ({len(report.with_projects)}):</b>\n{_names(report.with_projects)}\n\n"
        f"🏛 <b>Только конф./мероприятия ({len(report.with_conf_event_only)}):</b>\n{_names(report.with_conf_event_only)}\n\n"
        f"😴 <b>Нет ни одной заявки ({len(report.with_no_activity)}):</b>\n{_names(report.with_no_activity)}"
    )


async def send_report_for_month(
    bot: Bot, session: AsyncSession, config: Config, chat_id: int, year: int, month: int
) -> None:
    report = await build_month_report(session, config, year, month)
    await bot.send_message(chat_id, _format_report(report), reply_markup=back_to_admin_menu_keyboard())


@router.callback_query(F.data == "admin:report")
async def cb_report_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(REPORT_CHOOSE_MONTH, reply_markup=month_picker_keyboard("report"))
    await callback.answer()


@router.callback_query(F.data == "month:report:current")
async def cb_report_current(callback: CallbackQuery, session: AsyncSession, config: Config, bot: Bot) -> None:
    year, month = current_period(config.timezone)
    await send_report_for_month(bot, session, config, callback.message.chat.id, year, month)
    await callback.answer()


@router.callback_query(F.data == "month:report:previous")
async def cb_report_previous(callback: CallbackQuery, session: AsyncSession, config: Config, bot: Bot) -> None:
    year, month = previous_period(*current_period(config.timezone))
    await send_report_for_month(bot, session, config, callback.message.chat.id, year, month)
    await callback.answer()


@router.callback_query(F.data == "month:report:custom")
async def cb_report_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReportMonth.waiting_custom_month)
    await state.update_data(purpose="report")
    await callback.message.edit_text(ASK_CUSTOM_MONTH)
    await callback.answer()


@router.message(ReportMonth.waiting_custom_month)
async def process_custom_month(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, bot: Bot
) -> None:
    parsed = parse_month_string(message.text)
    if parsed is None:
        await message.answer(INVALID_MONTH_FORMAT)
        return

    year, month = parsed
    data = await state.get_data()
    purpose = data.get("purpose", "report")
    await state.clear()

    if purpose == "export":
        await send_export_for_month(bot, session, config, message.chat.id, year, month)
    else:
        await send_report_for_month(bot, session, config, message.chat.id, year, month)


@router.callback_query(F.data == "admin:activity")
async def cb_activity(callback: CallbackQuery, session: AsyncSession) -> None:
    report = await build_student_activity_report(session)
    await callback.message.edit_text(_format_activity(report), reply_markup=back_to_admin_menu_keyboard())
    await callback.answer()
