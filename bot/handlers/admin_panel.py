from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.filters.roles import IsAdmin
from bot.keyboards.admin import admin_menu_keyboard
from bot.utils.texts import MAIN_MENU_ADMIN

router = Router()
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "menu:admin")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext, is_super_admin: bool) -> None:
    await state.clear()
    await callback.message.edit_text(MAIN_MENU_ADMIN, reply_markup=admin_menu_keyboard(is_super_admin))
    await callback.answer()
