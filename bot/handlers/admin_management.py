from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.db.repo import users as users_repo
from bot.filters.roles import IsSuperAdmin
from bot.keyboards.admin import admin_list_keyboard, promote_confirm_keyboard
from bot.states.admin_promote import AdminPromote
from bot.utils.texts import (
    ADMIN_ASK_PROMOTE_TARGET,
    ADMIN_DEMOTE_DONE,
    ADMIN_PROMOTE_CONFIRM,
    ADMIN_PROMOTE_DONE,
    ADMIN_PROMOTE_NOT_REGISTERED,
)

router = Router()
router.message.filter(IsSuperAdmin())
router.callback_query.filter(IsSuperAdmin())


def _admin_list_text(admins: list[User]) -> str:
    if not admins:
        return "👑 <b>Администраторы</b>\n\nПока никто не назначен."
    return "👑 <b>Администраторы</b>"


async def _show_admin_list(message: Message, session: AsyncSession) -> None:
    admins = await users_repo.list_admins(session)
    await message.answer(_admin_list_text(admins), reply_markup=admin_list_keyboard(admins))


@router.callback_query(F.data == "admin:manage_admins")
async def cb_manage_admins(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    admins = await users_repo.list_admins(session)
    await callback.message.edit_text(_admin_list_text(admins), reply_markup=admin_list_keyboard(admins))
    await callback.answer()


@router.callback_query(F.data == "admin:promote_start")
async def cb_promote_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPromote.waiting_target)
    await callback.message.edit_text(ADMIN_ASK_PROMOTE_TARGET)
    await callback.answer()


@router.callback_query(F.data == "admin:promote_cancel")
async def cb_promote_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await _show_admin_list(callback.message, session)
    await callback.answer()


def _extract_target_telegram_id(message: Message) -> int | None:
    if message.forward_from is not None:
        return message.forward_from.id
    origin = getattr(message, "forward_origin", None)
    sender_user = getattr(origin, "sender_user", None)
    if sender_user is not None:
        return sender_user.id
    if message.text and message.text.strip().isdigit():
        return int(message.text.strip())
    return None


@router.message(AdminPromote.waiting_target)
async def process_promote_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_id = _extract_target_telegram_id(message)
    if telegram_id is None:
        await message.answer(ADMIN_ASK_PROMOTE_TARGET)
        return

    target = await users_repo.get_by_telegram_id(session, telegram_id)
    if target is None:
        await message.answer(ADMIN_PROMOTE_NOT_REGISTERED)
        return

    await state.update_data(target_user_id=target.id)
    await message.answer(
        ADMIN_PROMOTE_CONFIRM.format(full_name=target.full_name),
        reply_markup=promote_confirm_keyboard(target.id),
    )


@router.callback_query(F.data.startswith("admin:promote_confirm:"))
async def cb_promote_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    target_id = int(callback.data.split(":")[2])
    target = await session.get(User, target_id)
    await users_repo.set_role(session, target_id, "admin")
    await state.clear()
    await callback.message.edit_text(ADMIN_PROMOTE_DONE.format(full_name=target.full_name))
    await _show_admin_list(callback.message, session)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:demote:"))
async def cb_demote(callback: CallbackQuery, session: AsyncSession) -> None:
    target_id = int(callback.data.split(":")[2])
    target = await session.get(User, target_id)
    await users_repo.set_role(session, target_id, "student")
    await callback.message.edit_text(ADMIN_DEMOTE_DONE.format(full_name=target.full_name))
    await _show_admin_list(callback.message, session)
    await callback.answer()
