import datetime as dt

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import Supplement, User
from bot.db.repo import events as events_repo
from bot.db.repo import projects as projects_repo
from bot.db.repo import supplements as supplements_repo
from bot.filters.roles import IsRegistered
from bot.handlers.common import show_main_menu
from bot.keyboards.builders import button, markup, page_slice, short
from bot.keyboards.cards import request_card_keyboard
from bot.keyboards.common import cancel_keyboard
from bot.keyboards.events import event_picker_keyboard
from bot.keyboards.student import confirm_cancel_keyboard, profile_keyboard, submission_type_keyboard
from bot.services import review
from bot.states.registration import Registration
from bot.states.submission import Submission
from bot.utils.format import h
from bot.utils.input import MAX_DESCRIPTION_LEN, MAX_TITLE_LEN, read_input, take_state_data
from bot.utils.screen import show_long_screen, show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ASK_CONFERENCE_PROJECT,
    ASK_EVENT_SEARCH,
    ASK_EVENT_WHAT_DID,
    ASK_NEW_EVENT_DATE,
    ASK_NEW_EVENT_NAME,
    BACK_BUTTON,
    CANCEL_BUTTON,
    CARD_ALREADY_PROCESSED_ALERT,
    INVALID_DATE,
    KIND_BY_CODE,
    KIND_TEXT,
    MAIN_MENU_BUTTON,
    MY_SUBMISSIONS_EMPTY,
    MY_SUBMISSIONS_TITLE,
    NOTHING_FOUND,
    PICK_EVENT,
    PICK_EVENT_EMPTY,
    PROFILE_CARD,
    PROFILE_EDIT_START,
    SUBMISSION_CHOOSE_TYPE,
    SUBMISSION_CONFIRM,
    SUBMISSION_DUPLICATE,
    SUBMISSION_SENT,
    WITHDRAW_CONFIRM,
    WITHDRAW_DONE,
)
from bot.utils.time import parse_date

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())

ROLE_LABELS = {"student": "Студент", "admin": "Администратор"}


# --- Profile ------------------------------------------------------------------------------------------------------


@router.callback_query(F.data == "menu:profile")
async def cb_profile(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    current_user: User,
    is_super_admin: bool,
) -> None:
    memberships = await projects_repo.list_user_memberships(session, current_user.id)
    projects = ", ".join(f"«{h(m.project.name)}»" for m in memberships if m.end_period is None) or "—"
    role_label = "Супер-админ" if is_super_admin else ROLE_LABELS.get(current_user.role, current_user.role)
    text = PROFILE_CARD.format(
        full_name=h(current_user.full_name),
        group_number=h(current_user.group_number),
        role_label=role_label,
        projects=projects,
    )
    await show_screen(state, bot, callback.message.chat.id, text, profile_keyboard())
    await callback.answer()


@router.callback_query(F.data == "profile:edit")
async def cb_profile_edit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(Registration.waiting_last_name)
    await show_screen(state, bot, callback.message.chat.id, PROFILE_EDIT_START, cancel_keyboard())
    await callback.answer()


# --- My submissions -----------------------------------------------------------------------------------------------


async def show_my_submissions(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, user: User, notice: str | None = None
) -> None:
    await state.clear()
    submissions = await supplements_repo.list_for_student(session, user.id)
    if not submissions:
        text = MY_SUBMISSIONS_EMPTY
    else:
        lines = [MY_SUBMISSIONS_TITLE]
        for s in submissions:
            icon = KIND_TEXT[s.event.kind]["icon"]
            lines += ["", f"{icon} «{h(s.event.name)}» · {s.event.held_on:%d.%m.%Y}", review.status_text(s)]
        text = "\n".join(lines)
    if notice:
        text = f"{notice}\n\n{text}"

    withdraw_rows = [
        [button(f"↩️ Отозвать «{short(s.event.name, 28)}»", f"my:wd:{s.id}")]
        for s in submissions
        if s.status == "pending"
    ]
    keyboard = markup(*withdraw_rows, [button(MAIN_MENU_BUTTON, "menu:main")])
    await show_long_screen(state, bot, chat_id, text, keyboard)


async def _own_supplement(session: AsyncSession, user: User, supplement_id: str) -> Supplement | None:
    supplement = await supplements_repo.get(session, int(supplement_id))
    return supplement if supplement is not None and supplement.student_id == user.id else None


@router.callback_query(F.data == "menu:my_submissions")
async def cb_my_submissions(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
) -> None:
    await callback.answer()
    await show_my_submissions(state, bot, callback.message.chat.id, session, current_user)


@router.callback_query(F.data.regexp(r"^my:wd:\d+$"))
async def cb_withdraw_ask(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
) -> None:
    supplement = await _own_supplement(session, current_user, callback.data.split(":")[2])
    if supplement is None or supplement.status != "pending":
        await callback.answer(CARD_ALREADY_PROCESSED_ALERT, show_alert=True)
        return
    keyboard = markup([button("↩️ Да, отозвать", f"my:wdy:{supplement.id}"), button(BACK_BUTTON, "menu:my_submissions")])
    text = WITHDRAW_CONFIRM.format(title=h(supplement.event.name))
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^my:wdy:\d+$"))
async def cb_withdraw(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
) -> None:
    await callback.answer()
    supplement = await _own_supplement(session, current_user, callback.data.split(":")[2])
    ok = supplement is not None and await review.withdraw_request(bot, session, config, supplement.id)
    notice = WITHDRAW_DONE if ok else CARD_ALREADY_PROCESSED_ALERT
    await show_my_submissions(state, bot, callback.message.chat.id, session, current_user, notice)


# --- New request --------------------------------------------------------------------------------------------------


@router.callback_query(F.data == "menu:submit")
async def cb_submit_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await show_screen(state, bot, callback.message.chat.id, SUBMISSION_CHOOSE_TYPE, submission_type_keyboard())
    await callback.answer()


async def _show_picker(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, page: int, notice: str | None = None
) -> None:
    data = await state.get_data()
    kind, query = data["kind"], data.get("query")
    events = await events_repo.list_for_kind(session, kind, verified_only=True)
    if query:
        events = events_repo.search(events, query)
    items, page, pages = page_slice(events, page)

    words = KIND_TEXT[kind]
    text = (PICK_EVENT if events else PICK_EVENT_EMPTY).format(icon=words["icon"], acc=words["acc"])
    if query:
        text = f"🔎 «{h(query)}»{'' if events else ' — ' + NOTHING_FOUND}\n\n{text}"
    if notice:
        text = f"{notice}\n\n{text}"
    await state.set_state(Submission.choosing_event)
    await show_screen(state, bot, chat_id, text, event_picker_keyboard("sb", items, page, pages, "flow:cancel"))


@router.callback_query(F.data.regexp(r"^sb:k:[ce]$"))
async def cb_submit_kind(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    await state.update_data(kind=KIND_BY_CODE[callback.data[-1]])
    await _show_picker(state, bot, callback.message.chat.id, session, 0)
    await callback.answer()


@router.callback_query(Submission.choosing_event, F.data.regexp(r"^sb:l:\d+$"))
async def cb_picker_page(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _show_picker(state, bot, callback.message.chat.id, session, int(callback.data.split(":")[2]))
    await callback.answer()


@router.callback_query(Submission.choosing_event, F.data == "sb:q")
async def cb_picker_search(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(Submission.searching_event)
    await show_screen(state, bot, callback.message.chat.id, ASK_EVENT_SEARCH, cancel_keyboard())
    await callback.answer()


@router.message(Submission.searching_event)
async def process_picker_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    query = await read_input(message, state, MAX_TITLE_LEN, ASK_EVENT_SEARCH, cancel_keyboard())
    if query is None:
        return
    await state.update_data(query=query)
    await _show_picker(state, message.bot, message.chat.id, session, 0)


@router.callback_query(Submission.choosing_event, F.data.regexp(r"^sb:e:\d+$"))
async def cb_pick_event(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    current_user: User,
) -> None:
    await callback.answer()
    event = await events_repo.get(session, int(callback.data.split(":")[2]))
    data = await state.get_data()
    if event is None or event.is_archived or event.kind != data["kind"]:
        await _show_picker(state, bot, callback.message.chat.id, session, 0, notice=ACTION_EXPIRED)
        return
    if await supplements_repo.has_open_request(session, current_user.id, event.id):
        notice = SUBMISSION_DUPLICATE.format(name=h(event.name))
        await _show_picker(state, bot, callback.message.chat.id, session, 0, notice=notice)
        return
    await state.update_data(event_id=event.id)
    await _ask_details(state, bot, callback.message.chat.id, session, current_user)


@router.callback_query(Submission.choosing_event, F.data == "sb:new")
async def cb_new_event(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    kind = (await state.get_data())["kind"]
    await state.set_state(Submission.waiting_new_event_name)
    text = ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[kind]["gen"])
    await show_screen(state, bot, callback.message.chat.id, text, cancel_keyboard())
    await callback.answer()


@router.message(Submission.waiting_new_event_name)
async def process_new_event_name(message: Message, state: FSMContext) -> None:
    kind = (await state.get_data())["kind"]
    prompt = ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[kind]["gen"])
    name = await read_input(message, state, MAX_TITLE_LEN, prompt, cancel_keyboard())
    if name is None:
        return
    await state.update_data(new_event_name=name)
    await state.set_state(Submission.waiting_new_event_date)
    await show_screen(state, message.bot, message.chat.id, ASK_NEW_EVENT_DATE, cancel_keyboard())


@router.message(Submission.waiting_new_event_date)
async def process_new_event_date(
    message: Message, state: FSMContext, session: AsyncSession, current_user: User
) -> None:
    raw = await read_input(message, state, 20, ASK_NEW_EVENT_DATE, cancel_keyboard())
    if raw is None:
        return
    held_on = parse_date(raw)
    if held_on is None:
        text = f"{INVALID_DATE}\n\n{ASK_NEW_EVENT_DATE}"
        await show_screen(state, message.bot, message.chat.id, text, cancel_keyboard())
        return
    await state.update_data(new_event_date=held_on.isoformat(), event_id=None)
    await _ask_details(state, message.bot, message.chat.id, session, current_user)


async def _ask_details(state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, user: User) -> None:
    kind = (await state.get_data())["kind"]
    await state.set_state(Submission.waiting_details)
    if kind == "event":
        await show_screen(state, bot, chat_id, ASK_EVENT_WHAT_DID, cancel_keyboard())
        return
    memberships = await projects_repo.list_user_memberships(session, user.id)
    options = [m.project.name for m in memberships if m.end_period is None]
    await state.update_data(project_options=options)
    keyboard = markup(
        *[[button(f"📁 {short(name)}", f"sb:p:{i}")] for i, name in enumerate(options)],
        [button(CANCEL_BUTTON, "flow:cancel")],
    )
    await show_screen(state, bot, chat_id, ASK_CONFERENCE_PROJECT, keyboard)


async def _event_line_from_data(session: AsyncSession, data: dict) -> str | None:
    if data.get("event_id"):
        event = await events_repo.get(session, data["event_id"])
        return review.event_line(event.kind, event.name, event.held_on) if event else None
    held_on = dt.date.fromisoformat(data["new_event_date"])
    return review.event_line(data["kind"], data["new_event_name"], held_on, verified=False)


async def _show_confirm(state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession) -> None:
    data = await state.get_data()
    line = await _event_line_from_data(session, data)
    if line is None:
        await state.clear()
        await show_screen(state, bot, chat_id, ACTION_EXPIRED, markup([button(MAIN_MENU_BUTTON, "menu:main")]))
        return
    await state.set_state(Submission.confirm)
    text = SUBMISSION_CONFIRM.format(
        label=KIND_TEXT[data["kind"]]["label"],
        event_line=line,
        details=review.details_line(data["kind"], data.get("project_name"), data.get("what_did")),
    )
    await show_screen(state, bot, chat_id, text, confirm_cancel_keyboard("submit:confirm"))


@router.callback_query(Submission.waiting_details, F.data.regexp(r"^sb:p:\d+$"))
async def cb_pick_project_option(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    options = (await state.get_data()).get("project_options", [])
    index = int(callback.data.split(":")[2])
    if index >= len(options):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await state.update_data(project_name=options[index])
    await _show_confirm(state, bot, callback.message.chat.id, session)
    await callback.answer()


@router.message(Submission.waiting_details)
async def process_details(message: Message, state: FSMContext, session: AsyncSession) -> None:
    kind = (await state.get_data())["kind"]
    if kind == "conference":
        value = await read_input(message, state, MAX_TITLE_LEN, ASK_CONFERENCE_PROJECT, cancel_keyboard())
        field = "project_name"
    else:
        value = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_EVENT_WHAT_DID, cancel_keyboard())
        field = "what_did"
    if value is None:
        return
    await state.update_data(**{field: value})
    await _show_confirm(state, message.bot, message.chat.id, session)


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
    chat_id = callback.message.chat.id

    if data.get("event_id"):
        event = await events_repo.get(session, data["event_id"])
        if event is None or event.is_archived:
            await show_main_menu(state, bot, chat_id, is_admin, notice=ACTION_EXPIRED)
            return
        if await supplements_repo.has_open_request(session, current_user.id, event.id):
            await show_main_menu(state, bot, chat_id, is_admin, notice=SUBMISSION_DUPLICATE.format(name=h(event.name)))
            return
    else:
        held_on = dt.date.fromisoformat(data["new_event_date"])
        event = await events_repo.create(
            session, data["kind"], data["new_event_name"], held_on, current_user.id, verified=False
        )

    supplement = await supplements_repo.create_request(
        session,
        current_user.id,
        event.id,
        project_name=data.get("project_name"),
        what_did=data.get("what_did"),
    )
    await review.send_request_to_admins(bot, session, config, supplement, request_card_keyboard(supplement.id))
    await show_main_menu(state, bot, chat_id, is_admin, notice=SUBMISSION_SENT)
