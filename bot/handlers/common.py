from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.models import User
from bot.keyboards.common import back_to_main_menu_keyboard, main_menu_keyboard
from bot.states.registration import Registration
from bot.utils.format import h
from bot.utils.screen import delete_message, show_screen
from bot.utils.texts import (
    HELP_ADMIN_SUFFIX,
    HELP_TEXT,
    MAIN_MENU_ADMIN,
    MAIN_MENU_STUDENT,
    MENU_NOT_REGISTERED,
    WELCOME_BACK,
    WELCOME_NEW,
)

router = Router()


async def show_main_menu(
    state: FSMContext, bot: Bot, chat_id: int, is_admin: bool, *, notice: str | None = None, new: bool = False
) -> None:
    text = MAIN_MENU_ADMIN if is_admin else MAIN_MENU_STUDENT
    if notice:
        text = f"{notice}\n\n{text}"
    await show_screen(state, bot, chat_id, text, main_menu_keyboard(is_admin), new=new)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot, current_user: User | None, is_admin: bool) -> None:
    await state.clear()
    await delete_message(bot, message.chat.id, message.message_id)
    if current_user is None:
        await state.set_state(Registration.waiting_last_name)
        await show_screen(state, bot, message.chat.id, WELCOME_NEW, new=True)
        return
    greeting = WELCOME_BACK.format(full_name=h(current_user.full_name))
    await show_main_menu(state, bot, message.chat.id, is_admin, notice=greeting, new=True)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, bot: Bot, current_user: User | None, is_admin: bool) -> None:
    await state.clear()
    await delete_message(bot, message.chat.id, message.message_id)
    if current_user is None:
        await show_screen(state, bot, message.chat.id, MENU_NOT_REGISTERED, new=True)
        return
    await show_main_menu(state, bot, message.chat.id, is_admin, new=True)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, bot: Bot, current_user: User | None, is_admin: bool) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    markup = back_to_main_menu_keyboard() if current_user is not None else None
    text = HELP_TEXT + HELP_ADMIN_SUFFIX if is_admin else HELP_TEXT
    await show_screen(state, bot, message.chat.id, text, markup, new=True)


@router.callback_query(F.data.in_({"menu:main", "flow:cancel"}))
async def cb_main_menu(
    callback: CallbackQuery, state: FSMContext, bot: Bot, current_user: User | None, is_admin: bool
) -> None:
    await state.clear()
    await callback.answer()
    if current_user is not None:
        await show_main_menu(state, bot, callback.message.chat.id, is_admin)
