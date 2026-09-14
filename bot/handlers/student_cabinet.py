import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import Supplement, User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsRegistered
from bot.handlers.common import show_main_menu
from bot.keyboards.admin import approval_keyboard
from bot.keyboards.common import back_to_main_menu_keyboard, cancel_keyboard
from bot.keyboards.student import confirm_cancel_keyboard, profile_keyboard, submission_type_keyboard
from bot.states.registration import Registration
from bot.states.submission import Submission
from bot.utils.format import h, money
from bot.utils.input import MAX_DESCRIPTION_LEN, MAX_TITLE_LEN, read_input, take_state_data
from bot.utils.screen import show_long_screen, show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ADMIN_NEW_CONFERENCE_CARD,
    ADMIN_NEW_EVENT_CARD,
    ASK_CONFERENCE_NAME,
    ASK_CONFERENCE_PROJECT,
    ASK_EVENT_NAME,
    ASK_EVENT_WHAT_DID,
    MY_SUBMISSIONS_EMPTY,
    MY_SUBMISSIONS_TITLE,
    PROFILE_CARD,
    PROFILE_EDIT_START,
    SUBMISSION_CHOOSE_TYPE,
    SUBMISSION_CONFIRM_CONFERENCE,
    SUBMISSION_CONFIRM_EVENT,
    SUBMISSION_SENT,
)
from bot.utils.time import current_period

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())

MY_SUBMISSIONS_LIMIT = 20
ROLE_LABELS = {"student": "Студент", "admin": "Администратор"}
TYPE_LABELS = {"project": "📁 Проект", "conference": "🏛 Конференция", "event": "🎪 Мероприятие"}


def _submission_title(supplement: Supplement) -> str:
    if supplement.type == "conference":
        return supplement.conference_name or ""
    if supplement.type == "event":
        return supplement.event_name or ""
    return supplement.project_name or ""


def _submission_status(supplement: Supplement) -> str:
    if supplement.status == "approved":
        return f"✅ Одобрено — {money(supplement.amount)} BYN"
    if supplement.status == "rejected":
        reason = f": {h(supplement.reject_reason)}" if supplement.reject_reason else ""
        return f"❌ Отклонено{reason}"
    return "⏳ На рассмотрении"


@router.callback_query(F.data == "menu:profile")
async def cb_profile(
    callback: CallbackQuery, state: FSMContext, bot: Bot, current_user: User, is_super_admin: bool
) -> None:
    role_label = "Супер-админ" if is_super_admin else ROLE_LABELS.get(current_user.role, current_user.role)
    text = PROFILE_CARD.format(
        full_name=h(current_user.full_name),
        group_number=h(current_user.group_number),
        role_label=role_label,
    )
    await show_screen(state, bot, callback.message.chat.id, text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:edit")
async def cb_profile_edit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(Registration.waiting_last_name)
    await show_screen(state, bot, callback.message.chat.id, PROFILE_EDIT_START, cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:my_submissions")
async def cb_my_submissions(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
) -> None:
    await callback.answer()
    submissions = await supplements_repo.list_for_student(session, current_user.id, MY_SUBMISSIONS_LIMIT)
    if not submissions:
        text = MY_SUBMISSIONS_EMPTY
    else:
        lines = [MY_SUBMISSIONS_TITLE.format(limit=MY_SUBMISSIONS_LIMIT)]
        for s in submissions:
            lines.append("")
            lines.append(f"{TYPE_LABELS[s.type]} «{h(_submission_title(s))}» · {s.period_month:02d}.{s.period_year}")
            lines.append(_submission_status(s))
        text = "\n".join(lines)
    await show_long_screen(state, bot, callback.message.chat.id, text, back_to_main_menu_keyboard())


@router.callback_query(F.data == "menu:submit")
async def cb_submit_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(Submission.choosing_type)
    await show_screen(state, bot, callback.message.chat.id, SUBMISSION_CHOOSE_TYPE, submission_type_keyboard())
    await callback.answer()


@router.callback_query(Submission.choosing_type, F.data == "submit_type:conference")
async def cb_choose_conference(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(supplement_type="conference")
    await state.set_state(Submission.waiting_conference_name)
    await show_screen(state, bot, callback.message.chat.id, ASK_CONFERENCE_NAME, cancel_keyboard())
    await callback.answer()


@router.callback_query(Submission.choosing_type, F.data == "submit_type:event")
async def cb_choose_event(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(supplement_type="event")
    await state.set_state(Submission.waiting_event_name)
    await show_screen(state, bot, callback.message.chat.id, ASK_EVENT_NAME, cancel_keyboard())
    await callback.answer()


@router.message(Submission.waiting_conference_name)
async def process_conference_name(message: Message, state: FSMContext) -> None:
    value = await read_input(message, state, MAX_TITLE_LEN, ASK_CONFERENCE_NAME, cancel_keyboard())
    if value is None:
        return
    await state.update_data(conference_name=value)
    await state.set_state(Submission.waiting_conference_project_name)
    await show_screen(state, message.bot, message.chat.id, ASK_CONFERENCE_PROJECT, cancel_keyboard())


@router.message(Submission.waiting_conference_project_name)
async def process_conference_project(message: Message, state: FSMContext) -> None:
    value = await read_input(message, state, MAX_TITLE_LEN, ASK_CONFERENCE_PROJECT, cancel_keyboard())
    if value is None:
        return
    await state.update_data(project_name=value)
    data = await state.get_data()
    await state.set_state(Submission.confirm)
    text = SUBMISSION_CONFIRM_CONFERENCE.format(
        conference_name=h(data["conference_name"]), project_name=h(data["project_name"])
    )
    await show_screen(state, message.bot, message.chat.id, text, confirm_cancel_keyboard("submit:confirm"))


@router.message(Submission.waiting_event_name)
async def process_event_name(message: Message, state: FSMContext) -> None:
    value = await read_input(message, state, MAX_TITLE_LEN, ASK_EVENT_NAME, cancel_keyboard())
    if value is None:
        return
    await state.update_data(event_name=value)
    await state.set_state(Submission.waiting_event_what_did)
    await show_screen(state, message.bot, message.chat.id, ASK_EVENT_WHAT_DID, cancel_keyboard())


@router.message(Submission.waiting_event_what_did)
async def process_event_what_did(message: Message, state: FSMContext) -> None:
    value = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_EVENT_WHAT_DID, cancel_keyboard())
    if value is None:
        return
    await state.update_data(what_did=value)
    data = await state.get_data()
    await state.set_state(Submission.confirm)
    text = SUBMISSION_CONFIRM_EVENT.format(event_name=h(data["event_name"]), what_did=h(data["what_did"]))
    await show_screen(state, message.bot, message.chat.id, text, confirm_cancel_keyboard("submit:confirm"))


@router.callback_query(Submission.confirm, F.data == "submit:confirm")
async def cb_submit_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    is_admin: bool,
    bot: Bot,
    config: Config,
) -> None:
    data = await take_state_data(state, Submission.confirm)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()

    year, month = current_period(config.timezone)
    student_name, group = h(current_user.full_name), h(current_user.group_number)
    if data["supplement_type"] == "conference":
        supplement = await supplements_repo.create_conference(
            session, current_user.id, data["conference_name"], data["project_name"], year, month
        )
        card_text = ADMIN_NEW_CONFERENCE_CARD.format(
            full_name=student_name,
            group_number=group,
            conference_name=h(data["conference_name"]),
            project_name=h(data["project_name"]),
        )
    else:
        supplement = await supplements_repo.create_event(
            session, current_user.id, data["event_name"], data["what_did"], year, month
        )
        card_text = ADMIN_NEW_EVENT_CARD.format(
            full_name=student_name,
            group_number=group,
            event_name=h(data["event_name"]),
            what_did=h(data["what_did"]),
        )

    admin_ids = await users_repo.list_admin_telegram_ids(session, config.super_admin_id)
    keyboard = approval_keyboard(supplement.id)
    for admin_telegram_id in admin_ids:
        try:
            sent = await bot.send_message(admin_telegram_id, card_text, reply_markup=keyboard)
        except TelegramAPIError:
            logger.exception("Failed to deliver supplement %s card to admin %s", supplement.id, admin_telegram_id)
            continue
        await supplements_repo.add_notification(
            session, supplement.id, admin_telegram_id, sent.chat.id, sent.message_id
        )

    await show_main_menu(state, bot, callback.message.chat.id, is_admin, notice=SUBMISSION_SENT)
