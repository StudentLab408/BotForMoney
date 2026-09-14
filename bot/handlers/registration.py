from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import users as users_repo
from bot.handlers.common import show_main_menu
from bot.keyboards.common import cancel_keyboard
from bot.keyboards.student import registration_confirm_keyboard
from bot.states.registration import Registration
from bot.utils.format import h
from bot.utils.input import MAX_GROUP_LEN, MAX_NAME_LEN, read_input, take_state_data
from bot.utils.screen import show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ASK_FIRST_NAME,
    ASK_GROUP,
    ASK_LAST_NAME,
    ASK_MIDDLE_NAME,
    PROFILE_UPDATED,
    REGISTRATION_CONFIRM,
    REGISTRATION_DONE,
    REGISTRATION_RESTART,
)

router = Router()


def _prompt_markup(current_user: User | None) -> InlineKeyboardMarkup | None:
    # New users must finish registration; existing users editing their profile may cancel.
    return cancel_keyboard() if current_user is not None else None


@router.message(Registration.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext, current_user: User | None) -> None:
    markup = _prompt_markup(current_user)
    value = await read_input(message, state, MAX_NAME_LEN, ASK_LAST_NAME, markup)
    if value is None:
        return
    await state.update_data(last_name=value)
    await state.set_state(Registration.waiting_first_name)
    await show_screen(state, message.bot, message.chat.id, ASK_FIRST_NAME, markup)


@router.message(Registration.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext, current_user: User | None) -> None:
    markup = _prompt_markup(current_user)
    value = await read_input(message, state, MAX_NAME_LEN, ASK_FIRST_NAME, markup)
    if value is None:
        return
    await state.update_data(first_name=value)
    await state.set_state(Registration.waiting_middle_name)
    await show_screen(state, message.bot, message.chat.id, ASK_MIDDLE_NAME, markup)


@router.message(Registration.waiting_middle_name)
async def process_middle_name(message: Message, state: FSMContext, current_user: User | None) -> None:
    markup = _prompt_markup(current_user)
    value = await read_input(message, state, MAX_NAME_LEN, ASK_MIDDLE_NAME, markup)
    if value is None:
        return
    await state.update_data(middle_name=value)
    await state.set_state(Registration.waiting_group)
    await show_screen(state, message.bot, message.chat.id, ASK_GROUP, markup)


@router.message(Registration.waiting_group)
async def process_group(message: Message, state: FSMContext, current_user: User | None) -> None:
    value = await read_input(message, state, MAX_GROUP_LEN, ASK_GROUP, _prompt_markup(current_user))
    if value is None:
        return
    await state.update_data(group_number=value)
    data = await state.get_data()
    await state.set_state(Registration.confirm)
    text = REGISTRATION_CONFIRM.format(
        last_name=h(data["last_name"]),
        first_name=h(data["first_name"]),
        middle_name=h(data["middle_name"]),
        group_number=h(data["group_number"]),
    )
    markup = registration_confirm_keyboard(can_cancel=current_user is not None)
    await show_screen(state, message.bot, message.chat.id, text, markup)


@router.callback_query(Registration.confirm, F.data == "reg:retry")
async def retry_registration(callback: CallbackQuery, state: FSMContext, bot: Bot, current_user: User | None) -> None:
    await state.set_state(Registration.waiting_last_name)
    await show_screen(state, bot, callback.message.chat.id, REGISTRATION_RESTART, _prompt_markup(current_user))
    await callback.answer()


@router.callback_query(Registration.confirm, F.data == "reg:confirm")
async def confirm_registration(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    config: Config,
    current_user: User | None,
) -> None:
    data = await take_state_data(state, Registration.confirm)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()

    user = await users_repo.create_or_update(
        session,
        telegram_id=callback.from_user.id,
        last_name=data["last_name"],
        first_name=data["first_name"],
        middle_name=data["middle_name"],
        group_number=data["group_number"],
    )
    # The middleware computed is_admin before the profile existed, so derive it again.
    is_admin = user.telegram_id == config.super_admin_id or user.role == "admin"
    notice = PROFILE_UPDATED if current_user is not None else REGISTRATION_DONE.format(full_name=h(user.full_name))
    await show_main_menu(state, bot, callback.message.chat.id, is_admin, notice=notice)
