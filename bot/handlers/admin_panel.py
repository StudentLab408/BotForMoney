from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repo import supplements as supplements_repo
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
    session: AsyncSession,
    is_super_admin: bool,
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    await state.clear()
    text = f"{notice}\n\n{MAIN_MENU_ADMIN}" if notice else MAIN_MENU_ADMIN
    pending = await supplements_repo.count_pending(session)
    await show_screen(state, bot, chat_id, text, admin_menu_keyboard(is_super_admin, pending), new=new)


@router.callback_query(F.data == "menu:admin")
async def cb_admin_menu(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, is_super_admin: bool
) -> None:
    await show_admin_menu(state, bot, callback.message.chat.id, session, is_super_admin)
    await callback.answer()
