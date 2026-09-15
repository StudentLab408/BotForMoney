"""Decisions on requests and awards, shared by pushed cards, the admin queue and student cards.

Each decision updates the database first and then brings every admin's copy of the card and the student up to date.
"""

import datetime as dt
import logging
from decimal import Decimal

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import Supplement, User
from bot.db.repo import events as events_repo
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.services.explain import award_note
from bot.services.reporting import student_payouts
from bot.utils.format import h, money
from bot.utils.texts import (
    CARD_DELETED,
    CARD_PROCESSED_APPROVED,
    CARD_PROCESSED_REJECTED,
    CARD_STUDENT_ARCHIVED,
    CARD_WITHDRAWN,
    DETAIL_NO_WORK,
    DETAIL_NONE,
    DETAIL_WHAT_DID,
    DETAIL_WORK,
    EVENT_LINE,
    KIND_TEXT,
    PARTICIPATION_TEXT,
    PAYOUT_DETAILS_HINT,
    REASON_PART,
    REQUEST_CARD,
    STUDENT_NOTIFY_AMOUNT_CHANGED,
    STUDENT_NOTIFY_APPROVED,
    STUDENT_NOTIFY_CANCELLED,
    STUDENT_NOTIFY_REJECTED,
    UNVERIFIED_MARK,
)
from bot.utils.time import current_period, format_date, format_datetime, format_period

logger = logging.getLogger(__name__)


def event_line(kind: str, name: str, held_on: dt.date, *, verified: bool = True) -> str:
    line = EVENT_LINE.format(icon=KIND_TEXT[kind]["icon"], name=h(name), date=format_date(held_on))
    return line if verified else line + UNVERIFIED_MARK


def details_line(kind: str, participation: str | None, work_title: str | None, what_did: str | None) -> str:
    if kind == "conference":
        if not participation:
            return DETAIL_NO_WORK
        words = PARTICIPATION_TEXT[participation]
        return DETAIL_WORK.format(
            icon=words["icon"], label=words["label"], value=h(work_title) if work_title else DETAIL_NONE
        )
    return DETAIL_WHAT_DID.format(value=h(what_did) if what_did else DETAIL_NONE)


def request_card_text(supplement: Supplement, config: Config) -> str:
    event = supplement.event
    return REQUEST_CARD.format(
        label=KIND_TEXT[event.kind]["label"],
        full_name=h(supplement.student.full_name),
        group_number=h(supplement.student.group_number),
        event_line=event_line(event.kind, event.name, event.held_on, verified=event.is_verified),
        details=details_line(event.kind, supplement.participation, supplement.work_title, supplement.what_did),
        submitted=format_datetime(supplement.created_at, config.timezone),
    )


def status_text(supplement: Supplement) -> str:
    if supplement.status == "approved":
        return f"✅ Одобрено — {money(supplement.amount)} BYN за {format_period(supplement.period)}"
    if supplement.status == "cancelled":
        return "🚫 Начисление отменено" + (f": {h(supplement.cancel_reason)}" if supplement.cancel_reason else "")
    if supplement.status == "rejected":
        return "❌ Отклонена" + (f": {h(supplement.reject_reason)}" if supplement.reject_reason else "")
    return {"pending": "⏳ На рассмотрении", "withdrawn": "↩️ Отозвана"}[supplement.status]


def decision_lines(supplement: Supplement, config: Config) -> list[str]:
    """Who decided and when — kept even if that admin's account was deleted."""
    lines = []
    if supplement.reviewed_by_name and supplement.reviewed_at:
        verb = "Отклонил(а)" if supplement.status == "rejected" else "Одобрил(а)"
        when = format_datetime(supplement.reviewed_at, config.timezone)
        lines.append(f"👤 {verb}: {h(supplement.reviewed_by_name)} · {when}")
    if supplement.cancelled_by_name and supplement.cancelled_at:
        when = format_datetime(supplement.cancelled_at, config.timezone)
        lines.append(f"👤 Отменил(а): {h(supplement.cancelled_by_name)} · {when}")
    return lines


def _now_str(config: Config) -> str:
    return format_datetime(dt.datetime.now(dt.UTC), config.timezone)


async def notify(bot: Bot, telegram_id: int, text: str) -> None:
    try:
        await bot.send_message(telegram_id, text)
    except TelegramAPIError:
        logger.warning("Could not notify user %s", telegram_id)


async def send_request_to_admins(
    bot: Bot, session: AsyncSession, config: Config, supplement: Supplement, keyboard: InlineKeyboardMarkup
) -> None:
    text = request_card_text(supplement, config)
    for admin_telegram_id in await users_repo.list_admin_telegram_ids(session, config.super_admin_id):
        try:
            sent = await bot.send_message(admin_telegram_id, text, reply_markup=keyboard)
        except TelegramAPIError:
            logger.exception("Failed to deliver request %s to admin %s", supplement.id, admin_telegram_id)
            continue
        await supplements_repo.add_notification(
            session, supplement.id, admin_telegram_id, sent.chat.id, sent.message_id
        )


async def _stamp_cards(bot: Bot, session: AsyncSession, config: Config, supplement: Supplement, suffix: str) -> None:
    """Remove the buttons from every admin's copy of the card and append the decision."""
    text = request_card_text(supplement, config) + suffix
    for note in await supplements_repo.list_notifications(session, supplement.id):
        try:
            await bot.edit_message_text(text, chat_id=note.chat_id, message_id=note.message_id)
        except TelegramAPIError:
            logger.warning("Could not update card %s for admin %s", supplement.id, note.admin_telegram_id)


async def stamp_deleted_requests(
    bot: Bot, session: AsyncSession, config: Config, supplement_ids: tuple[int, ...]
) -> None:
    """Call before deleting pending requests, so admins' cards lose their buttons."""
    for supplement_id in supplement_ids:
        supplement = await supplements_repo.get(session, supplement_id)
        if supplement is not None:
            await _stamp_cards(bot, session, config, supplement, CARD_DELETED.format(date=_now_str(config)))


async def payout_note(session: AsyncSession, config: Config, student_id: int, period: int) -> str:
    """Explains, when needed, why an approved amount is not simply added to the month's total."""
    payout = (await student_payouts(session, config, student_id, [period]))[period]
    note = award_note(payout, config)
    return note + PAYOUT_DETAILS_HINT if note else ""


def _reason_part(reason: str | None) -> str:
    return REASON_PART.format(reason=h(reason)) if reason else ""


async def approve_request(
    bot: Bot, session: AsyncSession, config: Config, supplement_id: int, amount: Decimal, admin: User
) -> bool:
    """Approve into the current month (the month of approval). False if someone already decided."""
    if not await supplements_repo.approve(
        session, supplement_id, amount, current_period(config.timezone), admin.id, admin.full_name
    ):
        return False
    supplement = await supplements_repo.get(session, supplement_id)
    if not supplement.event.is_verified:
        await events_repo.update_fields(session, supplement.event, is_verified=True)

    suffix = CARD_PROCESSED_APPROVED.format(amount=money(amount), admin_name=h(admin.full_name), date=_now_str(config))
    await _stamp_cards(bot, session, config, supplement, suffix)
    text = STUDENT_NOTIFY_APPROVED.format(title=h(supplement.event.name), amount=money(amount))
    text += await payout_note(session, config, supplement.student_id, supplement.period)
    await notify(bot, supplement.student.telegram_id, text)
    return True


async def reject_request(
    bot: Bot, session: AsyncSession, config: Config, supplement_id: int, admin: User, reason: str | None
) -> bool:
    if not await supplements_repo.reject(session, supplement_id, admin.id, admin.full_name, reason):
        return False
    supplement = await supplements_repo.get(session, supplement_id)
    suffix = CARD_PROCESSED_REJECTED.format(
        admin_name=h(admin.full_name), date=_now_str(config), reason_part=_reason_part(reason)
    )
    await _stamp_cards(bot, session, config, supplement, suffix)
    text = STUDENT_NOTIFY_REJECTED.format(title=h(supplement.event.name), reason_part=_reason_part(reason))
    await notify(bot, supplement.student.telegram_id, text)
    return True


async def withdraw_request(
    bot: Bot, session: AsyncSession, config: Config, supplement_id: int, *, student_archived: bool = False
) -> bool:
    if not await supplements_repo.withdraw(session, supplement_id):
        return False
    supplement = await supplements_repo.get(session, supplement_id)
    template = CARD_STUDENT_ARCHIVED if student_archived else CARD_WITHDRAWN
    await _stamp_cards(bot, session, config, supplement, template.format(date=_now_str(config)))
    return True


async def cancel_award(bot: Bot, session: AsyncSession, supplement_id: int, admin: User, reason: str | None) -> bool:
    if not await supplements_repo.cancel(session, supplement_id, admin.id, admin.full_name, reason):
        return False
    supplement = await supplements_repo.get(session, supplement_id)
    text = STUDENT_NOTIFY_CANCELLED.format(title=h(supplement.event.name), reason_part=_reason_part(reason))
    await notify(bot, supplement.student.telegram_id, text)
    return True


async def change_award_amount(bot: Bot, session: AsyncSession, supplement_id: int, amount: Decimal) -> bool:
    current = await supplements_repo.get(session, supplement_id)
    if current is not None and current.status == "approved" and current.amount == amount:
        return True
    if not await supplements_repo.change_amount(session, supplement_id, amount):
        return False
    supplement = await supplements_repo.get(session, supplement_id)
    text = STUDENT_NOTIFY_AMOUNT_CHANGED.format(title=h(supplement.event.name), amount=money(amount))
    await notify(bot, supplement.student.telegram_id, text)
    return True
