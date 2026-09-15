from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repo import users as users_repo
from bot.filters.roles import IsSuperAdmin
from bot.keyboards.builders import button, markup, short
from bot.utils.screen import show_screen
from bot.utils.texts import ADMIN_LIST_EMPTY, ADMIN_LIST_TITLE, BACK_BUTTON

router = Router()
router.callback_query.filter(IsSuperAdmin())


async def show_admin_list(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, *, new: bool = False
) -> None:
    await state.clear()
    admins = await users_repo.list_admins(session)
    keyboard = markup(
        *[[button(f"👑 {short(a.full_name, 36)}", f"st:c:{a.id}")] for a in admins],
        [button("👥 К студентам", "st:v:all.0")],
        [button(BACK_BUTTON, "menu:admin")],
    )
    await show_screen(state, bot, chat_id, ADMIN_LIST_TITLE if admins else ADMIN_LIST_EMPTY, keyboard, new=new)


@router.callback_query(F.data == "admin:manage_admins")
async def cb_manage_admins(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await show_admin_list(state, bot, callback.message.chat.id, session)
    await callback.answer()
