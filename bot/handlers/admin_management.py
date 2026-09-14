from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageOriginUser
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import users as users_repo
from bot.filters.roles import IsSuperAdmin
from bot.keyboards.admin import admin_list_keyboard, confirm_keyboard
from bot.keyboards.common import cancel_keyboard
from bot.services.commands import sync_role_commands
from bot.states.admin_promote import AdminPromote
from bot.utils.format import h
from bot.utils.input import take_state_data
from bot.utils.screen import delete_message, show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ADMIN_ALREADY_ADMIN,
    ADMIN_ASK_PROMOTE_TARGET,
    ADMIN_DEMOTE_DONE,
    ADMIN_LIST_EMPTY,
    ADMIN_LIST_TITLE,
    ADMIN_PROMOTE_CONFIRM,
    ADMIN_PROMOTE_DONE,
    ADMIN_PROMOTE_NOT_FOUND,
)

router = Router()
router.message.filter(IsSuperAdmin())
router.callback_query.filter(IsSuperAdmin())


async def show_admin_list(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    await state.clear()
    admins = await users_repo.list_admins(session)
    text = ADMIN_LIST_TITLE if admins else ADMIN_LIST_EMPTY
    if notice:
        text = f"{notice}\n\n{text}"
    await show_screen(state, bot, chat_id, text, admin_list_keyboard(admins), new=new)


def _extract_target_telegram_id(message: Message) -> int | None:
    if isinstance(message.forward_origin, MessageOriginUser):
        return message.forward_origin.sender_user.id
    if message.text and message.text.strip().isdigit():
        return int(message.text.strip())
    return None


@router.callback_query(F.data == "admin:manage_admins")
async def cb_manage_admins(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await show_admin_list(state, bot, callback.message.chat.id, session)
    await callback.answer()


@router.callback_query(F.data == "admin:promote_start")
async def cb_promote_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminPromote.waiting_target)
    await show_screen(state, bot, callback.message.chat.id, ADMIN_ASK_PROMOTE_TARGET, cancel_keyboard())
    await callback.answer()


@router.message(AdminPromote.waiting_target)
async def process_promote_target(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    telegram_id = _extract_target_telegram_id(message)
    target = await users_repo.get_by_telegram_id(session, telegram_id) if telegram_id is not None else None

    if target is None:
        text = f"{ADMIN_PROMOTE_NOT_FOUND}\n\n{ADMIN_ASK_PROMOTE_TARGET}"
        await show_screen(state, bot, message.chat.id, text, cancel_keyboard())
        return
    if target.role == "admin":
        text = f"{ADMIN_ALREADY_ADMIN.format(full_name=h(target.full_name))}\n\n{ADMIN_ASK_PROMOTE_TARGET}"
        await show_screen(state, bot, message.chat.id, text, cancel_keyboard())
        return

    await state.update_data(target_user_id=target.id)
    await state.set_state(AdminPromote.confirm)
    text = ADMIN_PROMOTE_CONFIRM.format(full_name=h(target.full_name))
    await show_screen(state, bot, message.chat.id, text, confirm_keyboard("admin:promote_confirm"))


@router.callback_query(AdminPromote.confirm, F.data == "admin:promote_confirm")
async def cb_promote_confirm(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    data = await take_state_data(state, AdminPromote.confirm)
    target = await session.get(User, data["target_user_id"]) if data else None
    if target is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await users_repo.set_role(session, target.id, "admin")
    await sync_role_commands(bot, target.telegram_id, is_admin=True, config=config)
    notice = ADMIN_PROMOTE_DONE.format(full_name=h(target.full_name))
    await show_admin_list(state, bot, callback.message.chat.id, session, notice=notice)


@router.callback_query(F.data.startswith("admin:demote:"))
async def cb_demote(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    target = await session.get(User, int(callback.data.split(":")[2]))
    if target is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await users_repo.set_role(session, target.id, "student")
    # The super-admin keeps admin rights via config even without the DB role.
    still_admin = target.telegram_id == config.super_admin_id
    await sync_role_commands(bot, target.telegram_id, is_admin=still_admin, config=config)
    notice = ADMIN_DEMOTE_DONE.format(full_name=h(target.full_name))
    await show_admin_list(state, bot, callback.message.chat.id, session, notice=notice)
