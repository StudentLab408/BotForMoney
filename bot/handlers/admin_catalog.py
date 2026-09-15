"""Admin catalogs: projects with their members, conferences and events."""

from collections import Counter

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import deletion as deletion_repo
from bot.db.repo import events as events_repo
from bot.db.repo import projects as projects_repo
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_students import add_to_project, end_project_membership
from bot.keyboards.builders import button, markup, page_slice, pagination_row, short
from bot.keyboards.events import event_button_text
from bot.services import review
from bot.states.admin import EventForm, ProjectForm
from bot.utils.format import h, money
from bot.utils.input import MAX_DESCRIPTION_LEN, MAX_TITLE_LEN, read_input, take_state_data
from bot.utils.screen import recall, remember, show_long_screen, show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    ASK_EVENT_RENAME,
    ASK_NEW_EVENT_DATE,
    ASK_NEW_EVENT_NAME,
    ASK_PROJECT_NAME,
    ASK_PROJECT_REGALIA,
    BACK_BUTTON,
    CANCEL_BUTTON,
    CODE_BY_KIND,
    DELETE_BUTTON,
    DELETE_CONFIRM_BUTTON,
    DELETE_EVENT_CONFIRM,
    DELETE_PROJECT_CONFIRM,
    DELETE_UNDO_NOTE,
    EVENT_DELETED,
    EVENT_MERGE_CONFIRM,
    EVENT_MERGE_DUPLICATES,
    EVENT_MERGE_PICK,
    EVENT_MERGED,
    EVENT_SAVED,
    EVENTS_TITLE,
    INVALID_DATE,
    KIND_BY_CODE,
    KIND_TEXT,
    NOTHING_FOUND,
    PICK_MEMBER_TO_REMOVE,
    PICK_STUDENT_FOR_PROJECT,
    PROJECT_ARCHIVE_CONFIRM,
    PROJECT_ARCHIVED,
    PROJECT_DELETED,
    PROJECT_RESTORED,
    PROJECT_SAVED,
    PROJECTS_TITLE,
    SKIP_BUTTON,
)
from bot.utils.time import current_period, format_date, format_period, parse_date

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _id(callback: CallbackQuery, index: int = 2) -> int:
    return int(callback.data.split(":")[index])


# --- Projects -----------------------------------------------------------------------------------------------------


async def show_projects(
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
    projects = await projects_repo.list_all(session)
    member_counts = Counter(m.project_id for m in await projects_repo.list_current_memberships(session))
    items, page, pages = page_slice(projects, page)
    await remember(state, projects_page=page)
    rows = [
        [button(f"{'🗄 ' if p.is_archived else ''}📁 {short(p.name, 32)} · 👥{member_counts[p.id]}", f"pj:o:{p.id}")]
        for p in items
    ]
    text = PROJECTS_TITLE.format(count=len(projects)) + ("" if projects else f"\n\n{NOTHING_FOUND}")
    if notice:
        text = f"{notice}\n\n{text}"
    keyboard = markup(
        *rows,
        pagination_row(page, pages, lambda p: f"pj:l:{p}"),
        [button("➕ Новый проект", "pj:new")],
        [button(BACK_BUTTON, "menu:admin")],
    )
    await show_screen(state, bot, chat_id, text, keyboard, new=new)


async def show_project(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, project_id: int, notice: str | None = None
) -> None:
    await state.clear()
    project = await projects_repo.get(session, project_id)
    if project is None:
        await show_projects(state, bot, chat_id, session)
        return
    members = await projects_repo.list_members(session, project.id, current_only=False)
    current = [m for m in members if m.end_period is None]
    lines = [
        f"📁 <b>{h(project.name)}</b>" + (" · 🗄 в архиве" if project.is_archived else ""),
        f"🏅 Регалии: {h(project.regalia) if project.regalia else '—'}",
        "",
        f"👥 Участники ({len(current)}):",
        *[f"• {h(m.user.full_name)} ({h(m.user.group_number)}) — с {format_period(m.start_period)}" for m in current],
    ]
    if not current:
        lines.append("— никого —")
    past = len(members) - len(current)
    if past:
        lines.append(f"\nБывших участников: {past}")
    text = "\n".join(lines)
    if notice:
        text = f"{notice}\n\n{text}"

    active = not project.is_archived
    keyboard = markup(
        [button("➕ Участник", f"pj:add:{project.id}:0")]
        + ([button("➖ Участник", f"pj:rm:{project.id}")] if current else [])
        if active
        else None,
        [button("✏️ Название", f"pj:ren:{project.id}"), button("🏅 Регалии", f"pj:reg:{project.id}")],
        [
            button("🗄 В архив", f"pj:ar:{project.id}") if active else button("♻️ Восстановить", f"pj:unar:{project.id}"),
            button(DELETE_BUTTON, f"pj:del:{project.id}"),
        ],
        [button("⬅️ К проектам", f"pj:l:{await recall(state, 'projects_page', 0)}")],
    )
    await show_long_screen(state, bot, chat_id, text, keyboard)


@router.callback_query(F.data.regexp(r"^pj:l:\d+$"))
async def cb_projects(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await show_projects(state, bot, callback.message.chat.id, session, _id(callback))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^pj:o:\d+$"))
async def cb_project(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    await show_project(state, bot, callback.message.chat.id, session, _id(callback))


async def _ask_project_field(state: FSMContext, bot: Bot, chat_id: int, mode: str, project_id: int | None) -> None:
    await state.clear()
    await state.update_data(mode=mode, project_id=project_id)
    back = f"pj:o:{project_id}" if project_id else "pj:l:0"
    if mode == "regalia":
        await state.set_state(ProjectForm.waiting_regalia)
        keyboard = markup([button(SKIP_BUTTON, "pj:skip"), button(CANCEL_BUTTON, back)])
        await show_screen(state, bot, chat_id, ASK_PROJECT_REGALIA, keyboard)
    else:
        await state.set_state(ProjectForm.waiting_name)
        await show_screen(state, bot, chat_id, ASK_PROJECT_NAME, markup([button(CANCEL_BUTTON, back)]))


@router.callback_query(F.data == "pj:new")
async def cb_project_new(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await _ask_project_field(state, bot, callback.message.chat.id, "create", None)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^pj:(ren|reg):\d+$"))
async def cb_project_edit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    mode = "rename" if callback.data.split(":")[1] == "ren" else "regalia"
    await _ask_project_field(state, bot, callback.message.chat.id, mode, _id(callback))
    await callback.answer()


@router.message(ProjectForm.waiting_name)
async def process_project_name(message: Message, state: FSMContext, session: AsyncSession, current_user: User) -> None:
    data = await state.get_data()
    back = f"pj:o:{data['project_id']}" if data.get("project_id") else "pj:l:0"
    name = await read_input(message, state, MAX_TITLE_LEN, ASK_PROJECT_NAME, markup([button(CANCEL_BUTTON, back)]))
    if name is None:
        return
    if data["mode"] == "rename":
        project = await projects_repo.get(session, data["project_id"])
        await projects_repo.update_fields(session, project, name=name)
        await show_project(state, message.bot, message.chat.id, session, project.id, PROJECT_SAVED)
        return
    await state.update_data(name=name)
    await state.set_state(ProjectForm.waiting_regalia)
    keyboard = markup([button(SKIP_BUTTON, "pj:skip"), button(CANCEL_BUTTON, back)])
    await show_screen(state, message.bot, message.chat.id, ASK_PROJECT_REGALIA, keyboard)


async def _save_regalia(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, admin: User, regalia: str | None
) -> None:
    data = await take_state_data(state, ProjectForm.waiting_regalia)
    if data is None:
        return
    if data["mode"] == "create":
        project = await projects_repo.create(session, data["name"], regalia, admin.id)
    else:
        project = await projects_repo.get(session, data["project_id"])
        await projects_repo.update_fields(session, project, regalia=regalia)
    await show_project(state, bot, chat_id, session, project.id, PROJECT_SAVED)


@router.callback_query(ProjectForm.waiting_regalia, F.data == "pj:skip")
async def cb_project_skip_regalia(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
) -> None:
    await callback.answer()
    await _save_regalia(state, bot, callback.message.chat.id, session, current_user, None)


@router.message(ProjectForm.waiting_regalia)
async def process_project_regalia(
    message: Message, state: FSMContext, session: AsyncSession, current_user: User
) -> None:
    data = await state.get_data()
    back = f"pj:o:{data['project_id']}" if data.get("project_id") else "pj:l:0"
    keyboard = markup([button(SKIP_BUTTON, "pj:skip"), button(CANCEL_BUTTON, back)])
    regalia = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_PROJECT_REGALIA, keyboard)
    if regalia is not None:
        await _save_regalia(state, message.bot, message.chat.id, session, current_user, regalia)


@router.callback_query(F.data.regexp(r"^pj:add:\d+:\d+$"))
async def cb_project_pick_student(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    project = await projects_repo.get(session, _id(callback))
    if project is None:
        return
    member_ids = {m.user_id for m in await projects_repo.list_members(session, project.id, current_only=True)}
    candidates = [u for u in await users_repo.list_all(session) if u.id not in member_ids]
    items, page, pages = page_slice(candidates, _id(callback, 3))
    keyboard = markup(
        *[
            [button(f"{short(u.last_name + ' ' + u.first_name, 30)} · {u.group_number}", f"pj:as:{project.id}:{u.id}")]
            for u in items
        ],
        pagination_row(page, pages, lambda p: f"pj:add:{project.id}:{p}"),
        [button(BACK_BUTTON, f"pj:o:{project.id}")],
    )
    text = PICK_STUDENT_FOR_PROJECT.format(project=h(project.name)) + ("" if candidates else f"\n\n{NOTHING_FOUND}")
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)


@router.callback_query(F.data.regexp(r"^pj:as:\d+:\d+$"))
async def cb_project_add_student(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
) -> None:
    await callback.answer()
    user = await users_repo.get(session, _id(callback, 3))
    project_id = _id(callback)
    notice = (
        ACTION_EXPIRED
        if user is None or user.is_archived
        else await add_to_project(bot, session, config, user, project_id, current_user)
    )
    await show_project(state, bot, callback.message.chat.id, session, project_id, notice)


@router.callback_query(F.data.regexp(r"^pj:rm:\d+$"))
async def cb_project_pick_member(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    project = await projects_repo.get(session, _id(callback))
    if project is None:
        return
    members = await projects_repo.list_members(session, project.id, current_only=True)
    keyboard = markup(
        *[[button(f"➖ {short(m.user.full_name, 36)}", f"pj:rs:{m.id}")] for m in members],
        [button(BACK_BUTTON, f"pj:o:{project.id}")],
    )
    await show_screen(
        state, bot, callback.message.chat.id, PICK_MEMBER_TO_REMOVE.format(project=h(project.name)), keyboard
    )


@router.callback_query(F.data.regexp(r"^pj:rs:\d+$"))
async def cb_project_remove_member(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
) -> None:
    await callback.answer()
    member = await projects_repo.get_member(session, _id(callback))
    if member is None:
        return
    notice = await end_project_membership(bot, session, config, member, current_user)
    await show_project(state, bot, callback.message.chat.id, session, member.project_id, notice)


@router.callback_query(F.data.regexp(r"^pj:ar:\d+$"))
async def cb_project_archive_ask(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    project = await projects_repo.get(session, _id(callback))
    if project is None or project.is_archived:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    text = PROJECT_ARCHIVE_CONFIRM.format(name=h(project.name), period=format_period(current_period(config.timezone)))
    keyboard = markup([button("🗄 Да, в архив", f"pj:ary:{project.id}"), button(BACK_BUTTON, f"pj:o:{project.id}")])
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^pj:(ary|unar):\d+$"))
async def cb_project_archive(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
) -> None:
    await callback.answer()
    project = await projects_repo.get(session, _id(callback))
    if project is None:
        return
    archive = callback.data.split(":")[1] == "ary"
    if archive:
        for member in await projects_repo.list_members(session, project.id, current_only=True):
            await end_project_membership(bot, session, config, member, current_user)
    await projects_repo.update_fields(session, project, is_archived=archive)
    notice = (PROJECT_ARCHIVED if archive else PROJECT_RESTORED).format(name=h(project.name))
    await show_project(state, bot, callback.message.chat.id, session, project.id, notice)


# --- Conferences and events ---------------------------------------------------------------------------------------


async def show_events(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    kind: str,
    page: int = 0,
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    await state.clear()
    events = await events_repo.list_for_kind(session, kind, verified_only=False, include_archived=True)
    items, page, pages = page_slice(events, page)
    code = CODE_BY_KIND[kind]
    await remember(state, events_page=page)
    words = KIND_TEXT[kind]
    other = "event" if kind == "conference" else "conference"
    text = EVENTS_TITLE.format(icon=words["icon"], plural=words["plural"], count=len(events))
    if notice:
        text = f"{notice}\n\n{text}"
    keyboard = markup(
        *[[button(event_button_text(e), f"ev:o:{e.id}")] for e in items],
        pagination_row(page, pages, lambda p: f"ev:l:{code}:{p}"),
        [button(f"➕ Добавить {words['acc']}", f"ev:new:{code}")],
        [button(f"{KIND_TEXT[other]['icon']} {KIND_TEXT[other]['plural']}", f"ev:l:{CODE_BY_KIND[other]}:0")],
        [button(BACK_BUTTON, "menu:admin")],
    )
    await show_screen(state, bot, chat_id, text, keyboard, new=new)


async def show_event(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, event_id: int, notice: str | None = None
) -> None:
    await state.clear()
    event = await events_repo.get(session, event_id)
    if event is None:
        await show_events(state, bot, chat_id, session, "conference")
        return
    words = KIND_TEXT[event.kind]
    status = "🗄 в архиве" if event.is_archived else ("✅ подтверждено" if event.is_verified else "❔ не подтверждено")
    awards = await supplements_repo.list_for_event(session, event.id)
    lines = [
        f"{words['icon']} <b>{h(event.name)}</b>",
        f"📅 {format_date(event.held_on)} · {words['label']} · {status}",
        "",
        f"👥 Одобренные участники ({len(awards)}):",
        *[f"• {h(s.student.full_name)} — {money(s.amount)} BYN за {format_period(s.period)}" for s in awards],
    ]
    if not awards:
        lines.append("— никого —")
    text = "\n".join(lines)
    if notice:
        text = f"{notice}\n\n{text}"
    code = CODE_BY_KIND[event.kind]
    keyboard = markup(
        [button("✏️ Название", f"ev:ren:{event.id}"), button("📅 Дата", f"ev:dt:{event.id}")],
        [button("✅ Подтвердить", f"ev:ok:{event.id}")] if not event.is_verified and not event.is_archived else None,
        [button("🔀 Объединить с другой", f"ev:mg:{event.id}:0")] if not event.is_archived else None,
        [
            button("🗄 В архив", f"ev:ar:{event.id}")
            if not event.is_archived
            else button("♻️ Восстановить", f"ev:unar:{event.id}"),
            button(DELETE_BUTTON, f"ev:del:{event.id}"),
        ],
        [button(BACK_BUTTON, f"ev:l:{code}:{await recall(state, 'events_page', 0)}")],
    )
    await show_long_screen(state, bot, chat_id, text, keyboard)


@router.callback_query(F.data.regexp(r"^ev:l:[ce]:\d+$"))
async def cb_events(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    kind = KIND_BY_CODE[callback.data.split(":")[2]]
    await show_events(state, bot, callback.message.chat.id, session, kind, _id(callback, 3))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^ev:o:\d+$"))
async def cb_event(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    await show_event(state, bot, callback.message.chat.id, session, _id(callback))


@router.callback_query(F.data.regexp(r"^ev:(new:[ce]|ren:\d+|dt:\d+)$"))
async def cb_event_form(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    _, action, arg = callback.data.split(":")
    await state.clear()
    if action == "new":
        kind = KIND_BY_CODE[arg]
        await state.update_data(mode="create", kind=kind, event_id=None)
        await state.set_state(EventForm.waiting_name)
        text, back = ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[kind]["gen"]), f"ev:l:{arg}:0"
    else:
        event = await events_repo.get(session, int(arg))
        if event is None:
            await callback.answer(ACTION_EXPIRED, show_alert=True)
            return
        await state.update_data(mode=action, kind=event.kind, event_id=event.id)
        if action == "ren":
            await state.set_state(EventForm.waiting_name)
            text = ASK_EVENT_RENAME
        else:
            await state.set_state(EventForm.waiting_date)
            text = ASK_NEW_EVENT_DATE
        back = f"ev:o:{event.id}"
    await state.update_data(back=back)
    await show_screen(state, bot, callback.message.chat.id, text, markup([button(CANCEL_BUTTON, back)]))
    await callback.answer()


@router.message(EventForm.waiting_name)
async def process_event_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    prompt = (
        ASK_EVENT_RENAME if data["mode"] == "ren" else ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[data["kind"]]["gen"])
    )
    name = await read_input(message, state, MAX_TITLE_LEN, prompt, markup([button(CANCEL_BUTTON, data["back"])]))
    if name is None:
        return
    if data["mode"] == "ren":
        event = await events_repo.get(session, data["event_id"])
        await events_repo.update_fields(session, event, name=name)
        await show_event(state, message.bot, message.chat.id, session, event.id, EVENT_SAVED)
        return
    await state.update_data(name=name)
    await state.set_state(EventForm.waiting_date)
    await show_screen(
        state, message.bot, message.chat.id, ASK_NEW_EVENT_DATE, markup([button(CANCEL_BUTTON, data["back"])])
    )


@router.message(EventForm.waiting_date)
async def process_event_date(message: Message, state: FSMContext, session: AsyncSession, current_user: User) -> None:
    data = await state.get_data()
    keyboard = markup([button(CANCEL_BUTTON, data["back"])])
    raw = await read_input(message, state, 20, ASK_NEW_EVENT_DATE, keyboard)
    if raw is None:
        return
    held_on = parse_date(raw)
    if held_on is None:
        await show_screen(state, message.bot, message.chat.id, f"{INVALID_DATE}\n\n{ASK_NEW_EVENT_DATE}", keyboard)
        return
    await state.clear()
    if data["mode"] == "create":
        event = await events_repo.create(session, data["kind"], data["name"], held_on, current_user.id, verified=True)
    else:
        event = await events_repo.get(session, data["event_id"])
        await events_repo.update_fields(session, event, held_on=held_on)
    await show_event(state, message.bot, message.chat.id, session, event.id, EVENT_SAVED)


@router.callback_query(F.data.regexp(r"^ev:(ok|ar|unar):\d+$"))
async def cb_event_flags(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    event = await events_repo.get(session, _id(callback))
    if event is None:
        return
    action = callback.data.split(":")[1]
    fields = {"ok": {"is_verified": True}, "ar": {"is_archived": True}, "unar": {"is_archived": False}}[action]
    await events_repo.update_fields(session, event, **fields)
    await show_event(state, bot, callback.message.chat.id, session, event.id, EVENT_SAVED)


@router.callback_query(F.data.regexp(r"^ev:mg:\d+:\d+$"))
async def cb_event_merge_pick(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    source = await events_repo.get(session, _id(callback))
    if source is None:
        return
    targets = [
        e for e in await events_repo.list_for_kind(session, source.kind, verified_only=False) if e.id != source.id
    ]
    items, page, pages = page_slice(targets, _id(callback, 3))
    keyboard = markup(
        *[[button(event_button_text(e), f"ev:ms:{source.id}:{e.id}")] for e in items],
        pagination_row(page, pages, lambda p: f"ev:mg:{source.id}:{p}"),
        [button(BACK_BUTTON, f"ev:o:{source.id}")],
    )
    text = EVENT_MERGE_PICK.format(name=h(source.name)) + ("" if targets else f"\n\n{NOTHING_FOUND}")
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)


@router.callback_query(F.data.regexp(r"^ev:(ms|my):\d+:\d+$"))
async def cb_event_merge(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, current_user: User
) -> None:
    await callback.answer()
    source = await events_repo.get(session, _id(callback))
    target = await events_repo.get(session, _id(callback, 3))
    if (
        source is None
        or target is None
        or source.id == target.id
        or source.is_archived
        or target.is_archived
        or source.kind != target.kind
    ):
        return
    if callback.data.split(":")[1] == "ms":
        text = EVENT_MERGE_CONFIRM.format(source=h(source.name), target=h(target.name))
        keyboard = markup(
            [button("🔀 Да, объединить", f"ev:my:{source.id}:{target.id}"), button(BACK_BUTTON, f"ev:o:{source.id}")]
        )
        await show_screen(state, bot, callback.message.chat.id, text, keyboard)
        return
    closed = await events_repo.merge(session, source, target, current_user.id, current_user.full_name)
    notice = EVENT_MERGED.format(name=h(target.name))
    if closed:
        notice += EVENT_MERGE_DUPLICATES.format(count=closed)
    await show_event(state, bot, callback.message.chat.id, session, target.id, notice)


# --- Deletion -----------------------------------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^pj:del:\d+$"))
async def cb_project_delete_ask(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    project = await projects_repo.get(session, _id(callback))
    if project is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    impact = await deletion_repo.project_impact(session, project)
    text = DELETE_PROJECT_CONFIRM.format(name=h(project.name), memberships=impact.memberships) + DELETE_UNDO_NOTE
    keyboard = markup(
        [button(DELETE_CONFIRM_BUTTON, f"pj:dely:{project.id}")], [button(BACK_BUTTON, f"pj:o:{project.id}")]
    )
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^pj:dely:\d+$"))
async def cb_project_delete(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    project = await projects_repo.get(session, _id(callback))
    if project is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    name = project.name
    await deletion_repo.delete_project(session, project)
    page = await recall(state, "projects_page", 0)
    await show_projects(
        state, bot, callback.message.chat.id, session, page, notice=PROJECT_DELETED.format(name=h(name))
    )


@router.callback_query(F.data.regexp(r"^ev:del:\d+$"))
async def cb_event_delete_ask(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    event = await events_repo.get(session, _id(callback))
    if event is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    impact = await deletion_repo.event_impact(session, event)
    text = DELETE_EVENT_CONFIRM.format(name=h(event.name), supplements=impact.supplements, approved=impact.approved)
    keyboard = markup([button(DELETE_CONFIRM_BUTTON, f"ev:dely:{event.id}")], [button(BACK_BUTTON, f"ev:o:{event.id}")])
    await show_screen(state, bot, callback.message.chat.id, text + DELETE_UNDO_NOTE, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^ev:dely:\d+$"))
async def cb_event_delete(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    event = await events_repo.get(session, _id(callback))
    if event is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    impact = await deletion_repo.event_impact(session, event)
    await review.stamp_deleted_requests(bot, session, config, impact.pending_ids)
    name, kind = event.name, event.kind
    await deletion_repo.delete_event(session, event)
    page = await recall(state, "events_page", 0)
    notice = EVENT_DELETED.format(name=h(name))
    await show_events(state, bot, callback.message.chat.id, session, kind, page, notice=notice)
