from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.filters.roles import IsAdmin
from bot.handlers.admin_panel import show_admin_menu
from bot.keyboards.admin import back_to_admin_menu_keyboard, month_picker_keyboard
from bot.services.list_delivery import send_monthly_lists
from bot.services.reporting import MonthReport, build_doc_rows, build_month_report, build_student_activity_report
from bot.states.report_month import ReportMonth
from bot.utils.format import h, money
from bot.utils.input import read_input
from bot.utils.screen import show_long_screen, show_screen
from bot.utils.texts import (
    ASK_CUSTOM_MONTH,
    EXPORT_CHOOSE_MONTH,
    EXPORT_EMPTY,
    EXPORT_SENT,
    INVALID_MONTH_FORMAT,
    REPORT_CHOOSE_MONTH,
)
from bot.utils.time import current_period, month_name, parse_month_string, previous_period

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _format_report(report: MonthReport, config: Config) -> str:
    lines = [
        f"📊 <b>Отчёт за {month_name(report.month)} {report.year}</b>",
        "",
        f"👥 Студентов с начислениями: {report.student_count}",
        f"💰 Итого начислено: {money(report.total_amount)} BYN",
        "",
        f"📁 Проекты: {report.project_count} — {money(report.project_amount)} BYN",
        f"🏛 Конференции: {report.conference_count} — {money(report.conference_amount)} BYN",
        f"🎪 Мероприятия: {report.event_count} — {money(report.event_amount)} BYN",
    ]
    if report.students_capped:
        lines += ["", f"⚠️ Упёрлись в лимит {money(config.monthly_cap)} BYN: {report.students_capped}"]
    return "\n".join(lines)


def _format_names(users: list[User]) -> str:
    if not users:
        return "— никого —"
    return "\n".join(f"• {h(u.last_name)} {h(u.first_name)} ({h(u.group_number)})" for u in users)


async def _run_for_month(
    purpose: str,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    is_super_admin: bool,
    year: int,
    month: int,
) -> None:
    if purpose == "report":
        report = await build_month_report(session, config, year, month)
        await show_screen(state, bot, chat_id, _format_report(report, config), back_to_admin_menu_keyboard())
        return

    rows = await build_doc_rows(session, config, year, month)
    name = month_name(month)
    if not rows:
        notice = EXPORT_EMPTY.format(month_name=name, year=year)
        await show_admin_menu(state, bot, chat_id, is_super_admin, notice=notice)
        return
    await send_monthly_lists(bot, chat_id, year, month, rows)
    # new=True moves the menu below the files that were just sent.
    notice = EXPORT_SENT.format(month_name=name, year=year)
    await show_admin_menu(state, bot, chat_id, is_super_admin, notice=notice, new=True)


async def open_month_picker(state: FSMContext, bot: Bot, chat_id: int, purpose: str, *, new: bool = False) -> None:
    await state.clear()
    text = REPORT_CHOOSE_MONTH if purpose == "report" else EXPORT_CHOOSE_MONTH
    await show_screen(state, bot, chat_id, text, month_picker_keyboard(purpose), new=new)


async def show_activity(state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, *, new: bool = False) -> None:
    await state.clear()
    report = await build_student_activity_report(session)
    text = (
        "👥 <b>Активность студентов</b> (за всё время)\n\n"
        f"📁 <b>Есть проектная надбавка ({len(report.with_projects)}):</b>\n"
        f"{_format_names(report.with_projects)}\n\n"
        f"🏛 <b>Только конф./мероприятия ({len(report.with_conf_event_only)}):</b>\n"
        f"{_format_names(report.with_conf_event_only)}\n\n"
        f"😴 <b>Нет ни одной заявки ({len(report.with_no_activity)}):</b>\n"
        f"{_format_names(report.with_no_activity)}"
    )
    await show_long_screen(state, bot, chat_id, text, back_to_admin_menu_keyboard(), new=new)


@router.callback_query(F.data.in_({"admin:report", "admin:export"}))
async def cb_month_picker(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await open_month_picker(state, bot, callback.message.chat.id, callback.data.removeprefix("admin:"))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^month:(report|export):(current|previous|custom)$"))
async def cb_month(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    is_super_admin: bool,
) -> None:
    _, purpose, option = callback.data.split(":")
    chat_id = callback.message.chat.id
    await callback.answer()

    if option == "custom":
        await state.set_state(ReportMonth.waiting_custom_month)
        await state.update_data(purpose=purpose)
        await show_screen(state, bot, chat_id, ASK_CUSTOM_MONTH, back_to_admin_menu_keyboard())
        return

    year, month = current_period(config.timezone)
    if option == "previous":
        year, month = previous_period(year, month)
    await _run_for_month(purpose, state, bot, chat_id, session, config, is_super_admin, year, month)


@router.message(ReportMonth.waiting_custom_month)
async def process_custom_month(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    is_super_admin: bool,
) -> None:
    raw = await read_input(message, state, 20, ASK_CUSTOM_MONTH, back_to_admin_menu_keyboard())
    if raw is None:
        return
    parsed = parse_month_string(raw)
    if parsed is None:
        text = f"{INVALID_MONTH_FORMAT}\n\n{ASK_CUSTOM_MONTH}"
        await show_screen(state, bot, message.chat.id, text, back_to_admin_menu_keyboard())
        return

    purpose = (await state.get_data()).get("purpose", "report")
    await state.clear()
    year, month = parsed
    await _run_for_month(purpose, state, bot, message.chat.id, session, config, is_super_admin, year, month)


@router.callback_query(F.data == "admin:activity")
async def cb_activity(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    await show_activity(state, bot, callback.message.chat.id, session)
