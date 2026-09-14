from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db.models import User
from bot.handlers.common import show_main_menu
from bot.utils.screen import delete_message, show_screen
from bot.utils.texts import FALLBACK_CALLBACK, FALLBACK_REGISTERED, FALLBACK_UNREGISTERED

router = Router()


@router.message()
async def fallback_message(
    message: Message, state: FSMContext, bot: Bot, current_user: User | None, is_admin: bool
) -> None:
    await state.clear()
    await delete_message(bot, message.chat.id, message.message_id)
    if current_user is None:
        await show_screen(state, bot, message.chat.id, FALLBACK_UNREGISTERED, new=True)
        return
    await show_main_menu(state, bot, message.chat.id, is_admin, notice=FALLBACK_REGISTERED, new=True)


@router.callback_query()
async def fallback_callback(callback: CallbackQuery) -> None:
    await callback.answer(FALLBACK_CALLBACK, show_alert=True)
