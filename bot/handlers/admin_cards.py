"""Buttons on request cards pushed to admins. Not a screen router: the card itself must never be edited into a menu."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_requests import parse_amount, start_reject
from bot.services import review
from bot.utils.texts import APPROVED_ALERT, CARD_ALREADY_PROCESSED_ALERT, INVALID_AMOUNT_ALERT

router = Router()
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data.regexp(r"^sup:approve:\d+:[\d.]+$"))
async def cb_card_approve(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, config: Config, current_user: User
) -> None:
    _, _, supplement_id, raw_amount = callback.data.split(":")
    amount = parse_amount(raw_amount)
    if amount is None:
        await callback.answer(INVALID_AMOUNT_ALERT, show_alert=True)
        return
    if not await review.approve_request(bot, session, config, int(supplement_id), amount, current_user):
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return
    await callback.answer(APPROVED_ALERT)


@router.callback_query(F.data.regexp(r"^sup:reject:\d+$"))
async def cb_card_reject(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    supplement = await supplements_repo.get(session, int(callback.data.split(":")[2]))
    if supplement is None or supplement.status != "pending":
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return
    await start_reject(state, bot, callback.message.chat.id, supplement.id, "card")
    await callback.answer()
