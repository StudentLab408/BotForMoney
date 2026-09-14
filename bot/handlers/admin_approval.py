import datetime as dt
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS
from bot.db.models import Supplement, User
from bot.db.repo import supplements as supplements_repo
from bot.filters.roles import IsAdmin
from bot.keyboards.admin import reject_reason_keyboard
from bot.states.admin_reject import AdminReject
from bot.utils.texts import (
    ADMIN_NEW_CONFERENCE_CARD,
    ADMIN_NEW_EVENT_CARD,
    CARD_ALREADY_PROCESSED_ALERT,
    CARD_PROCESSED_APPROVED,
    CARD_PROCESSED_REJECTED,
    STUDENT_NOTIFY_APPROVED,
    STUDENT_NOTIFY_REJECTED,
)

router = Router()
router.callback_query.filter(IsAdmin())


def _basis_title(supplement: Supplement) -> str:
    return supplement.conference_name if supplement.type == "conference" else supplement.event_name


def _rebuild_card_text(supplement: Supplement, student: User) -> str:
    if supplement.type == "conference":
        return ADMIN_NEW_CONFERENCE_CARD.format(
            full_name=student.full_name,
            group_number=student.group_number,
            conference_name=supplement.conference_name,
            project_name=supplement.project_name,
        )
    return ADMIN_NEW_EVENT_CARD.format(
        full_name=student.full_name,
        group_number=student.group_number,
        event_name=supplement.event_name,
        what_did=supplement.what_did,
    )


async def _stamp_all_cards(bot: Bot, session: AsyncSession, supplement: Supplement, student: User, suffix: str) -> None:
    base_text = _rebuild_card_text(supplement, student)
    notifications = await supplements_repo.list_notifications(session, supplement.id)
    for note in notifications:
        try:
            await bot.edit_message_text(chat_id=note.chat_id, message_id=note.message_id, text=base_text + suffix)
        except Exception:
            pass


@router.callback_query(F.data.startswith("sup:approve:"))
async def cb_approve(callback: CallbackQuery, session: AsyncSession, current_user: User, bot: Bot) -> None:
    _, _, supplement_id_str, amount_str = callback.data.split(":")
    supplement_id = int(supplement_id_str)
    amount = Decimal(amount_str)

    if amount not in ALLOWED_CONF_EVENT_AMOUNTS:
        await callback.answer("⚠️ Некорректная сумма.", show_alert=True)
        return

    ok = await supplements_repo.approve(session, supplement_id, amount, current_user.id)
    if not ok:
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return

    supplement = await supplements_repo.get(session, supplement_id)
    student = await session.get(User, supplement.student_id)

    now_str = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    suffix = CARD_PROCESSED_APPROVED.format(amount=amount, admin_name=current_user.full_name, date=now_str)
    await _stamp_all_cards(bot, session, supplement, student, suffix)

    if student is not None:
        try:
            await bot.send_message(
                student.telegram_id,
                STUDENT_NOTIFY_APPROVED.format(title=_basis_title(supplement), amount=amount),
            )
        except Exception:
            pass

    await callback.answer("✅ Одобрено")


@router.callback_query(F.data.startswith("sup:reject:"))
async def cb_reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    supplement_id = int(callback.data.split(":")[2])
    await state.update_data(reject_supplement_id=supplement_id)
    await state.set_state(AdminReject.waiting_reason)
    await callback.message.reply(
        "Укажите причину отказа (или нажмите «Пропустить»).", reply_markup=reject_reason_keyboard()
    )
    await callback.answer()


async def _finalize_reject(
    bot: Bot, session: AsyncSession, supplement_id: int, admin: User, reason: str | None
) -> bool:
    ok = await supplements_repo.reject(session, supplement_id, admin.id, reason)
    if not ok:
        return False

    supplement = await supplements_repo.get(session, supplement_id)
    student = await session.get(User, supplement.student_id)

    now_str = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    reason_part = f"\nПричина: {reason}" if reason else ""
    suffix = CARD_PROCESSED_REJECTED.format(admin_name=admin.full_name, date=now_str, reason_part=reason_part)
    await _stamp_all_cards(bot, session, supplement, student, suffix)

    if student is not None:
        try:
            await bot.send_message(
                student.telegram_id,
                STUDENT_NOTIFY_REJECTED.format(title=_basis_title(supplement), reason_part=reason_part),
            )
        except Exception:
            pass
    return True


@router.callback_query(AdminReject.waiting_reason, F.data == "reject:skip")
async def cb_reject_skip(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, current_user: User, bot: Bot
) -> None:
    data = await state.get_data()
    supplement_id = data["reject_supplement_id"]
    await state.clear()
    ok = await _finalize_reject(bot, session, supplement_id, current_user, None)
    await callback.message.edit_text("❌ Заявка отклонена." if ok else CARD_ALREADY_PROCESSED_ALERT)
    await callback.answer()


@router.message(AdminReject.waiting_reason)
async def process_reject_reason(
    message: Message, state: FSMContext, session: AsyncSession, current_user: User, bot: Bot
) -> None:
    data = await state.get_data()
    supplement_id = data["reject_supplement_id"]
    await state.clear()
    ok = await _finalize_reject(bot, session, supplement_id, current_user, message.text.strip())
    await message.answer("❌ Заявка отклонена." if ok else CARD_ALREADY_PROCESSED_ALERT)
