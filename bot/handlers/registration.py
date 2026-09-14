from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repo import users as users_repo
from bot.handlers.common import show_main_menu
from bot.keyboards.student import registration_confirm_keyboard
from bot.states.registration import Registration
from bot.utils.texts import (
    ASK_FIRST_NAME,
    ASK_GROUP,
    ASK_MIDDLE_NAME,
    REGISTRATION_CONFIRM,
    REGISTRATION_DONE,
    REGISTRATION_RESTART,
)

router = Router()


@router.message(Registration.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext) -> None:
    await state.update_data(last_name=message.text.strip())
    await state.set_state(Registration.waiting_first_name)
    await message.answer(ASK_FIRST_NAME)


@router.message(Registration.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext) -> None:
    await state.update_data(first_name=message.text.strip())
    await state.set_state(Registration.waiting_middle_name)
    await message.answer(ASK_MIDDLE_NAME)


@router.message(Registration.waiting_middle_name)
async def process_middle_name(message: Message, state: FSMContext) -> None:
    await state.update_data(middle_name=message.text.strip())
    await state.set_state(Registration.waiting_group)
    await message.answer(ASK_GROUP)


@router.message(Registration.waiting_group)
async def process_group(message: Message, state: FSMContext) -> None:
    await state.update_data(group_number=message.text.strip())
    data = await state.get_data()
    await state.set_state(Registration.confirm)
    await message.answer(REGISTRATION_CONFIRM.format(**data), reply_markup=registration_confirm_keyboard())


@router.callback_query(Registration.confirm, F.data == "reg:retry")
async def retry_registration(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.waiting_last_name)
    await callback.message.edit_text(REGISTRATION_RESTART)
    await callback.answer()


@router.callback_query(Registration.confirm, F.data == "reg:confirm")
async def confirm_registration(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, is_admin: bool
) -> None:
    data = await state.get_data()
    user = await users_repo.create_or_update(
        session,
        telegram_id=callback.from_user.id,
        last_name=data["last_name"],
        first_name=data["first_name"],
        middle_name=data["middle_name"],
        group_number=data["group_number"],
    )
    await state.clear()
    await callback.message.edit_text(REGISTRATION_DONE.format(full_name=user.full_name))
    await show_main_menu(callback.message, user, is_admin)
    await callback.answer()
