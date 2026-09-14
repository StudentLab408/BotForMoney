from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsAdmin
from bot.keyboards.admin import admin_menu_keyboard, project_confirm_keyboard, student_search_results_keyboard
from bot.states.admin_project_entry import AdminProjectEntry
from bot.utils.texts import (
    ADMIN_ASK_PROJECT_NAME,
    ADMIN_ASK_REGALIA,
    ADMIN_ASK_STUDENT_SEARCH,
    ADMIN_PROJECT_CONFIRM,
    ADMIN_PROJECT_DONE,
    ADMIN_STUDENT_NOT_FOUND,
    MAIN_MENU_ADMIN,
)
from bot.utils.time import current_period

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:project_entry")
async def cb_start_project_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminProjectEntry.choosing_student)
    await callback.message.edit_text(ADMIN_ASK_STUDENT_SEARCH)
    await callback.answer()


@router.callback_query(F.data == "admin:cancel_project_entry")
async def cb_cancel_project_entry(callback: CallbackQuery, state: FSMContext, is_super_admin: bool) -> None:
    await state.clear()
    await callback.message.edit_text(MAIN_MENU_ADMIN, reply_markup=admin_menu_keyboard(is_super_admin))
    await callback.answer()


@router.message(AdminProjectEntry.choosing_student)
async def process_student_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    students = await users_repo.search_by_last_name(session, message.text.strip())
    if not students:
        await message.answer(ADMIN_STUDENT_NOT_FOUND)
        return
    await message.answer("Выберите студента:", reply_markup=student_search_results_keyboard(students))


@router.callback_query(AdminProjectEntry.choosing_student, F.data.startswith("admin:pick_student:"))
async def cb_pick_student(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[2])
    await state.update_data(student_id=student_id)
    await state.set_state(AdminProjectEntry.waiting_project_name)
    await callback.message.edit_text(ADMIN_ASK_PROJECT_NAME)
    await callback.answer()


@router.message(AdminProjectEntry.waiting_project_name)
async def process_project_name(message: Message, state: FSMContext) -> None:
    await state.update_data(project_name=message.text.strip())
    await state.set_state(AdminProjectEntry.waiting_regalia)
    await message.answer(ADMIN_ASK_REGALIA)


@router.message(AdminProjectEntry.waiting_regalia)
async def process_regalia(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(regalia=message.text.strip())
    data = await state.get_data()
    student = await session.get(User, data["student_id"])
    await state.set_state(AdminProjectEntry.confirm)
    await message.answer(
        ADMIN_PROJECT_CONFIRM.format(
            full_name=student.full_name,
            group_number=student.group_number,
            project_name=data["project_name"],
            regalia=data["regalia"],
        ),
        reply_markup=project_confirm_keyboard(),
    )


@router.callback_query(AdminProjectEntry.confirm, F.data == "admin:project_confirm")
async def cb_project_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    config: Config,
    is_super_admin: bool,
) -> None:
    data = await state.get_data()
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
    await state.clear()
    await callback.message.edit_text(ADMIN_PROJECT_DONE.format(full_name=student.full_name))
    await callback.message.answer(MAIN_MENU_ADMIN, reply_markup=admin_menu_keyboard(is_super_admin))
    await callback.answer()
