from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.filters.roles import IsAdmin
from bot.keyboards.admin import admin_menu_keyboard
from bot.utils.screen import show_screen
from bot.utils.texts import MAIN_MENU_ADMIN

router = Router()
router.callback_query.filter(IsAdmin())


async def show_admin_menu(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    is_super_admin: bool,
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    text = f"{notice}\n\n{MAIN_MENU_ADMIN}" if notice else MAIN_MENU_ADMIN
    await show_screen(state, bot, chat_id, text, admin_menu_keyboard(is_super_admin), new=new)


@router.callback_query(F.data == "menu:admin")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext, bot: Bot, is_super_admin: bool) -> None:
    await state.clear()
    await show_admin_menu(state, bot, callback.message.chat.id, is_super_admin)
    await callback.answer()
