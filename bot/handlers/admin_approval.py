import datetime as dt
import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS, Config
from bot.db.models import Supplement, User
from bot.db.repo import supplements as supplements_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_panel import show_admin_menu
from bot.keyboards.admin import reject_reason_keyboard
from bot.states.admin_reject import AdminReject
from bot.utils.format import h, money
from bot.utils.input import MAX_DESCRIPTION_LEN, read_input, take_state_data
from bot.utils.screen import show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ADMIN_NEW_CONFERENCE_CARD,
    ADMIN_NEW_EVENT_CARD,
    APPROVED_ALERT,
    ASK_REJECT_REASON,
    CARD_ALREADY_PROCESSED_ALERT,
    CARD_PROCESSED_APPROVED,
    CARD_PROCESSED_REJECTED,
    INVALID_AMOUNT_ALERT,
    REJECT_DONE,
    STUDENT_NOTIFY_APPROVED,
    STUDENT_NOTIFY_REJECTED,
)
from bot.utils.time import format_datetime

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _basis_title(supplement: Supplement) -> str:
    title = supplement.conference_name if supplement.type == "conference" else supplement.event_name
    return h(title or "")


def _rebuild_card_text(supplement: Supplement, student: User) -> str:
    if supplement.type == "conference":
        return ADMIN_NEW_CONFERENCE_CARD.format(
            full_name=h(student.full_name),
            group_number=h(student.group_number),
            conference_name=h(supplement.conference_name),
            project_name=h(supplement.project_name),
        )
    return ADMIN_NEW_EVENT_CARD.format(
        full_name=h(student.full_name),
        group_number=h(student.group_number),
        event_name=h(supplement.event_name),
        what_did=h(supplement.what_did),
    )


async def _stamp_all_cards(bot: Bot, session: AsyncSession, supplement: Supplement, student: User, suffix: str) -> None:
    """Remove the buttons from every admin's copy of the card and append the decision."""
    text = _rebuild_card_text(supplement, student) + suffix
    for note in await supplements_repo.list_notifications(session, supplement.id):
        try:
            await bot.edit_message_text(text, chat_id=note.chat_id, message_id=note.message_id)
        except TelegramAPIError:
            logger.warning("Could not update card %s for admin %s", supplement.id, note.admin_telegram_id)


async def _notify_student(bot: Bot, student: User, text: str) -> None:
    try:
        await bot.send_message(student.telegram_id, text)
    except TelegramAPIError:
        logger.warning("Could not notify student %s", student.telegram_id)


def _now_str(config: Config) -> str:
    return format_datetime(dt.datetime.now(dt.UTC), config.timezone)


@router.callback_query(F.data.startswith("sup:approve:"))
async def cb_approve(
    callback: CallbackQuery, session: AsyncSession, current_user: User, bot: Bot, config: Config
) -> None:
    try:
        _, _, supplement_id_str, amount_str = callback.data.split(":")
        supplement_id, amount = int(supplement_id_str), Decimal(amount_str)
    except (ValueError, InvalidOperation):
        await callback.answer(INVALID_AMOUNT_ALERT, show_alert=True)
        return
    if amount not in ALLOWED_CONF_EVENT_AMOUNTS:
        await callback.answer(INVALID_AMOUNT_ALERT, show_alert=True)
        return

    if not await supplements_repo.approve(session, supplement_id, amount, current_user.id):
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return
    await callback.answer(APPROVED_ALERT)

    supplement = await supplements_repo.get(session, supplement_id)
    student = await session.get(User, supplement.student_id)
    suffix = CARD_PROCESSED_APPROVED.format(
        amount=money(amount), admin_name=h(current_user.full_name), date=_now_str(config)
    )
    await _stamp_all_cards(bot, session, supplement, student, suffix)
    await _notify_student(
        bot, student, STUDENT_NOTIFY_APPROVED.format(title=_basis_title(supplement), amount=money(amount))
    )


@router.callback_query(F.data.startswith("sup:reject:"))
async def cb_reject_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    try:
        supplement_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    supplement = await supplements_repo.get(session, supplement_id)
    if supplement is None or supplement.status != "pending":
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminReject.waiting_reason)
    await state.update_data(reject_supplement_id=supplement_id)
    # new=True: the prompt appears right under the card instead of editing a menu far above.
    await show_screen(state, bot, callback.message.chat.id, ASK_REJECT_REASON, reject_reason_keyboard(), new=True)
    await callback.answer()


async def _finalize_reject(
    bot: Bot, session: AsyncSession, config: Config, supplement_id: int, admin: User, reason: str | None
) -> bool:
    if not await supplements_repo.reject(session, supplement_id, admin.id, reason):
        return False

    supplement = await supplements_repo.get(session, supplement_id)
    student = await session.get(User, supplement.student_id)
    reason_part = f"\nПричина: {h(reason)}" if reason else ""
    suffix = CARD_PROCESSED_REJECTED.format(
        admin_name=h(admin.full_name), date=_now_str(config), reason_part=reason_part
    )
    await _stamp_all_cards(bot, session, supplement, student, suffix)
    await _notify_student(
        bot, student, STUDENT_NOTIFY_REJECTED.format(title=_basis_title(supplement), reason_part=reason_part)
    )
    return True


@router.callback_query(AdminReject.waiting_reason, F.data == "reject:skip")
async def cb_reject_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    bot: Bot,
    config: Config,
    is_super_admin: bool,
) -> None:
    data = await take_state_data(state, AdminReject.waiting_reason)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    ok = await _finalize_reject(bot, session, config, data["reject_supplement_id"], current_user, None)
    notice = REJECT_DONE if ok else CARD_ALREADY_PROCESSED_ALERT
    await show_admin_menu(state, bot, callback.message.chat.id, is_super_admin, notice=notice)


@router.message(AdminReject.waiting_reason)
async def process_reject_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    bot: Bot,
    config: Config,
    is_super_admin: bool,
) -> None:
    reason = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_REJECT_REASON, reject_reason_keyboard())
    if reason is None:
        return
    data = await take_state_data(state, AdminReject.waiting_reason)
    if data is None:
        return
    ok = await _finalize_reject(bot, session, config, data["reject_supplement_id"], current_user, reason)
    notice = REJECT_DONE if ok else CARD_ALREADY_PROCESSED_ALERT
    await show_admin_menu(state, bot, message.chat.id, is_super_admin, notice=notice)
