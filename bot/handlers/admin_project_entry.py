from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_panel import show_admin_menu
from bot.keyboards.admin import confirm_keyboard, student_search_results_keyboard
from bot.keyboards.common import cancel_keyboard
from bot.states.admin_project_entry import AdminProjectEntry
from bot.utils.format import h, money
from bot.utils.input import MAX_DESCRIPTION_LEN, MAX_NAME_LEN, MAX_TITLE_LEN, read_input, take_state_data
from bot.utils.screen import show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ADMIN_ASK_PROJECT_NAME,
    ADMIN_ASK_REGALIA,
    ADMIN_ASK_STUDENT_SEARCH,
    ADMIN_CHOOSE_STUDENT,
    ADMIN_PROJECT_CONFIRM,
    ADMIN_PROJECT_DONE,
    ADMIN_STUDENT_NOT_FOUND,
)
from bot.utils.time import current_period

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:project_entry")
async def cb_start_project_entry(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(AdminProjectEntry.choosing_student)
    await show_screen(state, bot, callback.message.chat.id, ADMIN_ASK_STUDENT_SEARCH, cancel_keyboard())
    await callback.answer()


@router.message(AdminProjectEntry.choosing_student)
async def process_student_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    query = await read_input(message, state, MAX_NAME_LEN, ADMIN_ASK_STUDENT_SEARCH, cancel_keyboard())
    if query is None:
        return
    students = await users_repo.search_by_last_name(session, query)
    if not students:
        text = f"{ADMIN_STUDENT_NOT_FOUND}\n\n{ADMIN_ASK_STUDENT_SEARCH}"
        await show_screen(state, message.bot, message.chat.id, text, cancel_keyboard())
        return
    await show_screen(
        state, message.bot, message.chat.id, ADMIN_CHOOSE_STUDENT, student_search_results_keyboard(students)
    )


@router.callback_query(AdminProjectEntry.choosing_student, F.data.startswith("admin:pick_student:"))
async def cb_pick_student(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(student_id=int(callback.data.split(":")[2]))
    await state.set_state(AdminProjectEntry.waiting_project_name)
    await show_screen(state, bot, callback.message.chat.id, ADMIN_ASK_PROJECT_NAME, cancel_keyboard())
    await callback.answer()


@router.message(AdminProjectEntry.waiting_project_name)
async def process_project_name(message: Message, state: FSMContext) -> None:
    value = await read_input(message, state, MAX_TITLE_LEN, ADMIN_ASK_PROJECT_NAME, cancel_keyboard())
    if value is None:
        return
    await state.update_data(project_name=value)
    await state.set_state(AdminProjectEntry.waiting_regalia)
    await show_screen(state, message.bot, message.chat.id, ADMIN_ASK_REGALIA, cancel_keyboard())


@router.message(AdminProjectEntry.waiting_regalia)
async def process_regalia(
    message: Message, state: FSMContext, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    value = await read_input(message, state, MAX_DESCRIPTION_LEN, ADMIN_ASK_REGALIA, cancel_keyboard())
    if value is None:
        return
    await state.update_data(regalia=value)
    data = await state.get_data()
    student = await session.get(User, data["student_id"])
    if student is None:
        await state.clear()
        await show_admin_menu(state, message.bot, message.chat.id, is_super_admin, notice=ACTION_EXPIRED)
        return

    await state.set_state(AdminProjectEntry.confirm)
    text = ADMIN_PROJECT_CONFIRM.format(
        full_name=h(student.full_name),
        group_number=h(student.group_number),
        project_name=h(data["project_name"]),
        regalia=h(data["regalia"]),
        amount=money(config.project_amount),
    )
    await show_screen(state, message.bot, message.chat.id, text, confirm_keyboard("admin:project_confirm"))


@router.callback_query(AdminProjectEntry.confirm, F.data == "admin:project_confirm")
async def cb_project_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    current_user: User,
    config: Config,
    is_super_admin: bool,
) -> None:
    data = await take_state_data(state, AdminProjectEntry.confirm)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()

    student = await session.get(User, data["student_id"])
    year, month = current_period(config.timezone)
    await supplements_repo.create_project(
        session,
        student_id=student.id,
        admin_id=current_user.id,
        project_name=data["project_name"],
        regalia=data["regalia"],
        amount=config.project_amount,
        period_year=year,
        period_month=month,
    )
    notice = ADMIN_PROJECT_DONE.format(full_name=h(student.full_name))
    await show_admin_menu(state, bot, callback.message.chat.id, is_super_admin, notice=notice)
