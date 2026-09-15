"""The admin queue of pending requests, and the reject-reason form used from the queue and from pushed cards."""

from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS, Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_panel import show_admin_menu
from bot.keyboards.admin import amount_row
from bot.keyboards.builders import button, markup, page_slice, pagination_row, short
from bot.services import review
from bot.states.admin import AdminReject
from bot.utils.format import money
from bot.utils.input import MAX_DESCRIPTION_LEN, read_input, take_state_data
from bot.utils.screen import recall, remember, show_screen
from bot.utils.texts import (
    APPROVE_DONE,
    ASK_REJECT_REASON,
    BACK_BUTTON,
    CANCEL_BUTTON,
    CARD_ALREADY_PROCESSED_ALERT,
    INVALID_AMOUNT_ALERT,
    KIND_TEXT,
    QUEUE_EMPTY,
    QUEUE_TITLE,
    REJECT_DONE,
    SKIP_BUTTON,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def parse_amount(raw: str) -> Decimal | None:
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    return amount if amount in ALLOWED_CONF_EVENT_AMOUNTS else None


async def show_queue(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    page: int = 0,
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    await state.clear()
    pending = await supplements_repo.list_pending(session)
    items, page, pages = page_slice(pending, page)
    await remember(state, queue_page=page)

    text = QUEUE_TITLE.format(count=len(pending)) if pending else QUEUE_EMPTY
    if notice:
        text = f"{notice}\n\n{text}"
    rows = [
        [
            button(
                f"{KIND_TEXT[s.event.kind]['icon']} {s.student.short_name} — {short(s.event.name, 26)}", f"rq:o:{s.id}"
            )
        ]
        for s in items
    ]
    keyboard = markup(*rows, pagination_row(page, pages, lambda p: f"rq:l:{p}"), [button(BACK_BUTTON, "menu:admin")])
    await show_screen(state, bot, chat_id, text, keyboard, new=new)


async def start_reject(state: FSMContext, bot: Bot, chat_id: int, supplement_id: int, origin: str) -> None:
    """Ask for a reject reason. origin is 'queue' or 'card' and decides where to return afterwards."""
    await state.clear()
    await state.set_state(AdminReject.waiting_reason)
    await state.update_data(supplement_id=supplement_id, origin=origin)
    keyboard = markup(
        [button(SKIP_BUTTON, "reject:skip"), button(CANCEL_BUTTON, "rq:l:0" if origin == "queue" else "menu:admin")]
    )
    # From a pushed card the prompt appears under the card instead of editing a menu far above.
    await show_screen(state, bot, chat_id, ASK_REJECT_REASON, keyboard, new=origin == "card")


@router.callback_query(F.data.regexp(r"^rq:l:\d+$"))
async def cb_queue(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await show_queue(state, bot, callback.message.chat.id, session, int(callback.data.split(":")[2]))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^rq:o:\d+$"))
async def cb_open_request(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    await callback.answer()
    supplement = await supplements_repo.get(session, int(callback.data.split(":")[2]))
    page = await recall(state, "queue_page", 0)
    if supplement is None or supplement.status != "pending":
        await show_queue(state, bot, callback.message.chat.id, session, page, notice=CARD_ALREADY_PROCESSED_ALERT)
        return
    keyboard = markup(
        amount_row(lambda amount: f"rq:ok:{supplement.id}:{amount}"),
        [button("❌ Отклонить", f"rq:no:{supplement.id}")],
        [button("👤 Карточка студента", f"st:c:{supplement.student_id}")],
        [button(BACK_BUTTON, f"rq:l:{page}")],
    )
    await show_screen(state, bot, callback.message.chat.id, review.request_card_text(supplement, config), keyboard)


@router.callback_query(F.data.regexp(r"^rq:ok:\d+:[\d.]+$"))
async def cb_queue_approve(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
) -> None:
    _, _, supplement_id, raw_amount = callback.data.split(":")
    amount = parse_amount(raw_amount)
    if amount is None:
        await callback.answer(INVALID_AMOUNT_ALERT, show_alert=True)
        return
    await callback.answer()
    ok = await review.approve_request(bot, session, config, int(supplement_id), amount, current_user)
    notice = APPROVE_DONE.format(amount=money(amount)) if ok else CARD_ALREADY_PROCESSED_ALERT
    page = await recall(state, "queue_page", 0)
    await show_queue(state, bot, callback.message.chat.id, session, page, notice=notice)


@router.callback_query(F.data.regexp(r"^rq:no:\d+$"))
async def cb_queue_reject(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await start_reject(state, bot, callback.message.chat.id, int(callback.data.split(":")[2]), "queue")
    await callback.answer()


async def _finish_reject(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    admin: User,
    is_super_admin: bool,
    data: dict,
    reason: str | None,
) -> None:
    ok = await review.reject_request(bot, session, config, data["supplement_id"], admin, reason)
    notice = REJECT_DONE if ok else CARD_ALREADY_PROCESSED_ALERT
    if data["origin"] == "queue":
        await show_queue(state, bot, chat_id, session, await recall(state, "queue_page", 0), notice=notice)
    else:
        await show_admin_menu(state, bot, chat_id, session, is_super_admin, notice=notice)


@router.callback_query(AdminReject.waiting_reason, F.data == "reject:skip")
async def cb_reject_skip(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    data = await take_state_data(state, AdminReject.waiting_reason)
    if data is None:
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return
    await callback.answer()
    chat_id = callback.message.chat.id
    await _finish_reject(state, bot, chat_id, session, config, current_user, is_super_admin, data, None)


@router.message(AdminReject.waiting_reason)
async def process_reject_reason(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    origin = (await state.get_data()).get("origin", "card")
    cancel_cb = "rq:l:0" if origin == "queue" else "menu:admin"
    keyboard = markup([button(SKIP_BUTTON, "reject:skip"), button(CANCEL_BUTTON, cancel_cb)])
    reason = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_REJECT_REASON, keyboard)
    if reason is None:
        return
    data = await take_state_data(state, AdminReject.waiting_reason)
    if data is None:
        return
    await _finish_reject(state, bot, message.chat.id, session, config, current_user, is_super_admin, data, reason)
