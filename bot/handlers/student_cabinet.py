from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsRegistered
from bot.handlers.common import show_main_menu
from bot.keyboards.admin import approval_keyboard
from bot.keyboards.student import confirm_cancel_keyboard, submission_type_keyboard
from bot.states.submission import Submission
from bot.utils.texts import (
    ADMIN_NEW_CONFERENCE_CARD,
    ADMIN_NEW_EVENT_CARD,
    ASK_CONFERENCE_NAME,
    ASK_CONFERENCE_PROJECT,
    ASK_EVENT_NAME,
    ASK_EVENT_WHAT_DID,
    PROFILE_CARD,
    SUBMISSION_CHOOSE_TYPE,
    SUBMISSION_CONFIRM_CONFERENCE,
    SUBMISSION_CONFIRM_EVENT,
    SUBMISSION_SENT,
)
from bot.utils.time import current_period

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())

ROLE_LABELS = {"student": "Студент", "admin": "Администратор"}


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, current_user: User) -> None:
    await callback.message.edit_text(
        PROFILE_CARD.format(
            full_name=current_user.full_name,
            group_number=current_user.group_number,
            role_label=ROLE_LABELS.get(current_user.role, current_user.role),
        ),
        reply_markup=None,
    )
    await callback.answer()


@router.callback_query(F.data == "menu:submit")
async def cb_submit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Submission.choosing_type)
    await callback.message.edit_text(SUBMISSION_CHOOSE_TYPE, reply_markup=submission_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "submit:cancel")
async def cb_submit_cancel(
    callback: CallbackQuery, state: FSMContext, current_user: User, is_admin: bool
) -> None:
    await state.clear()
    await callback.answer()
    await show_main_menu(callback.message, current_user, is_admin)


@router.callback_query(Submission.choosing_type, F.data == "submit_type:conference")
async def cb_choose_conference(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(supplement_type="conference")
    await state.set_state(Submission.waiting_conference_name)
    await callback.message.edit_text(ASK_CONFERENCE_NAME)
    await callback.answer()


@router.callback_query(Submission.choosing_type, F.data == "submit_type:event")
async def cb_choose_event(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(supplement_type="event")
    await state.set_state(Submission.waiting_event_name)
    await callback.message.edit_text(ASK_EVENT_NAME)
    await callback.answer()


@router.message(Submission.waiting_conference_name)
async def process_conference_name(message: Message, state: FSMContext) -> None:
    await state.update_data(conference_name=message.text.strip())
    await state.set_state(Submission.waiting_conference_project_name)
    await message.answer(ASK_CONFERENCE_PROJECT)


@router.message(Submission.waiting_conference_project_name)
async def process_conference_project(message: Message, state: FSMContext) -> None:
    await state.update_data(project_name=message.text.strip())
    data = await state.get_data()
    await state.set_state(Submission.confirm)
    await message.answer(
        SUBMISSION_CONFIRM_CONFERENCE.format(**data),
        reply_markup=confirm_cancel_keyboard("submit:confirm", "submit:cancel"),
    )


@router.message(Submission.waiting_event_name)
async def process_event_name(message: Message, state: FSMContext) -> None:
    await state.update_data(event_name=message.text.strip())
    await state.set_state(Submission.waiting_event_what_did)
    await message.answer(ASK_EVENT_WHAT_DID)


@router.message(Submission.waiting_event_what_did)
async def process_event_what_did(message: Message, state: FSMContext) -> None:
    await state.update_data(what_did=message.text.strip())
    data = await state.get_data()
    await state.set_state(Submission.confirm)
    await message.answer(
        SUBMISSION_CONFIRM_EVENT.format(**data),
        reply_markup=confirm_cancel_keyboard("submit:confirm", "submit:cancel"),
    )


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
    data = await state.get_data()
    year, month = current_period(config.timezone)

    if data["supplement_type"] == "conference":
        supplement = await supplements_repo.create_conference(
            session, current_user.id, data["conference_name"], data["project_name"], year, month
        )
        card_text = ADMIN_NEW_CONFERENCE_CARD.format(
            full_name=current_user.full_name,
            group_number=current_user.group_number,
            conference_name=data["conference_name"],
            project_name=data["project_name"],
        )
    else:
        supplement = await supplements_repo.create_event(
            session, current_user.id, data["event_name"], data["what_did"], year, month
        )
        card_text = ADMIN_NEW_EVENT_CARD.format(
            full_name=current_user.full_name,
            group_number=current_user.group_number,
            event_name=data["event_name"],
            what_did=data["what_did"],
        )

    admin_ids = await users_repo.list_admin_telegram_ids(session, config.super_admin_id)
    keyboard = approval_keyboard(supplement.id)
    for admin_telegram_id in admin_ids:
        try:
            sent = await bot.send_message(admin_telegram_id, card_text, reply_markup=keyboard)
        except Exception:
            continue
        await supplements_repo.add_notification(session, supplement.id, admin_telegram_id, sent.chat.id, sent.message_id)

    await state.clear()
    await callback.message.edit_text(SUBMISSION_SENT)
    await show_main_menu(callback.message, current_user, is_admin)
    await callback.answer()
