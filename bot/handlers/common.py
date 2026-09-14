from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.models import User
from bot.keyboards.common import main_menu_keyboard
from bot.states.registration import Registration
from bot.utils.texts import MAIN_MENU_ADMIN, MAIN_MENU_STUDENT, WELCOME_BACK, WELCOME_NEW

router = Router()


async def show_main_menu(message: Message, current_user: User, is_admin: bool) -> None:
    text = MAIN_MENU_ADMIN if is_admin else MAIN_MENU_STUDENT
    greeting = WELCOME_BACK.format(full_name=current_user.full_name)
    await message.answer(f"{greeting}\n\n{text}", reply_markup=main_menu_keyboard(is_admin))


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, current_user: User | None, is_admin: bool) -> None:
    await state.clear()
    if current_user is None:
        await state.set_state(Registration.waiting_last_name)
        await message.answer(WELCOME_NEW)
        return
    await show_main_menu(message, current_user, is_admin)


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(
    callback: CallbackQuery, state: FSMContext, current_user: User | None, is_admin: bool
) -> None:
    await state.clear()
    await callback.answer()
    if current_user is None or callback.message is None:
        return
    text = MAIN_MENU_ADMIN if is_admin else MAIN_MENU_STUDENT
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(is_admin))
