"""Admin "Students" section: filtered list, student card, history, awards, projects, role and archive."""

import datetime as dt

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import ProjectMember, Supplement, User
from bot.db.repo import deletion as deletion_repo
from bot.db.repo import events as events_repo
from bot.db.repo import projects as projects_repo
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.filters.roles import IsAdmin
from bot.handlers.admin_requests import parse_amount
from bot.keyboards.admin import amount_row
from bot.keyboards.builders import PAGE_SIZE, button, markup, page_slice, pagination_row, short
from bot.keyboards.events import event_picker_keyboard
from bot.services import review
from bot.services.commands import sync_role_commands
from bot.services.explain import membership_span, month_block, month_title, paid_until_text
from bot.services.reporting import StudentStats, build_student_stats, list_users_for_filter, student_payouts
from bot.states.admin import AdminAward, AdminCancelAward, StudentSearch
from bot.utils.format import h, money
from bot.utils.input import MAX_DESCRIPTION_LEN, MAX_NAME_LEN, MAX_TITLE_LEN, read_input, take_state_data
from bot.utils.screen import recall, remember, show_long_screen, show_screen
from bot.utils.texts import (
    ACTION_EXPIRED,
    AMOUNT_CHANGED,
    ARCHIVE_CONFIRM,
    ARCHIVED_DONE,
    ASK_CANCEL_REASON,
    ASK_EVENT_SEARCH,
    ASK_NEW_EVENT_DATE,
    ASK_NEW_EVENT_NAME,
    ASK_STUDENT_SEARCH,
    AWARD_ASK_PROJECT,
    AWARD_ASK_WHAT_DID,
    AWARD_CONFIRM,
    AWARD_DONE,
    AWARD_PICK_AMOUNT,
    AWARD_PICK_EVENT,
    BACK_BUTTON,
    CANCEL_BUTTON,
    CANCEL_DONE,
    CARD_ALREADY_PROCESSED_ALERT,
    CONFIRM_BUTTON,
    CONFIRM_END_MEMBERSHIP,
    DELETE_ADMIN_NOTE,
    DELETE_BUTTON,
    DELETE_CONFIRM_BUTTON,
    DELETE_STUDENT_CONFIRM,
    DELETE_UNDO_NOTE,
    FILTER_LABELS,
    GROUPS_TITLE,
    INVALID_DATE,
    KIND_BY_CODE,
    KIND_TEXT,
    MEMBERSHIP_ENDED,
    NO_PROJECTS,
    NOT_ADDED_BECAUSE_PROJECT_ADMIN,
    NOTHING_FOUND,
    PICK_MEMBERSHIP_TO_END,
    PICK_NEW_AMOUNT,
    PICK_PROJECT_FOR_STUDENT,
    PROJECT_MEMBER_ADDED,
    PROJECT_MEMBER_EXISTS,
    ROLE_CONFIRM_DEMOTE,
    ROLE_CONFIRM_PROMOTE,
    ROLE_DEMOTED,
    ROLE_PROMOTED,
    SKIP_BUTTON,
    STUDENT_DELETED,
    STUDENT_HISTORY_EMPTY,
    STUDENT_HISTORY_TITLE,
    STUDENT_NOTIFY_AWARD,
    STUDENT_NOTIFY_PROJECT_ADDED,
    STUDENT_NOTIFY_PROJECT_REMOVED,
    STUDENTS_TITLE,
    SUBMISSION_DUPLICATE,
    UNARCHIVED_DONE,
)
from bot.utils.time import current_period, format_period, parse_date, period_title

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

FILTER_BUTTONS = [
    [("Все", "all"), ("📁 Проекты", "proj"), ("✅ Конф.", "conf")],
    [("😴 Без активности", "idle"), ("🗄 Архив", "arch")],
]


def _can_remove(user: User, viewer_is_super_admin: bool, config: Config) -> bool:
    """Archiving/deleting removes admin rights: only the super-admin may do it to an admin, and never to themselves."""
    if user.telegram_id == config.super_admin_id:
        return False
    return viewer_is_super_admin or user.role != "admin"


def _markers(user: User, stats: StudentStats, config: Config) -> str:
    marks = ""
    if user.is_archived:
        marks += "🗄"
    if user.role == "admin" or user.telegram_id == config.super_admin_id:
        marks += "👑"
    if stats.current_projects:
        marks += "📁"
    if stats.approved:
        marks += f"✅{stats.approved}"
    if stats.pending:
        marks += f"⏳{stats.pending}"
    if not marks and stats.is_idle:
        marks = "😴"
    return marks


# --- List ---------------------------------------------------------------------------------------------------------


def _parse_view(view: str) -> tuple[str, int | None, int]:
    """'all.0' -> ('all', None, 0); 'grp.3.1' -> ('grp', 3, 1)."""
    parts = view.split(".")
    if parts[0] == "grp" and len(parts) == 3:
        return "grp", int(parts[1]), int(parts[2])
    return parts[0], None, int(parts[-1]) if len(parts) > 1 else 0


async def show_students(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    view: str = "all.0",
    *,
    notice: str | None = None,
    new: bool = False,
) -> None:
    await state.clear()
    filter_code, group_index, page = _parse_view(view)
    stats = await build_student_stats(session)

    if filter_code == "q":
        query = str(await recall(state, "students_query", ""))
        users = users_repo.search(
            await users_repo.list_all(session) + await users_repo.list_all(session, archived=True), query
        )
        label = FILTER_LABELS["q"].format(query=h(query))
    elif filter_code == "grp":
        groups = await users_repo.list_groups(session)
        group = groups[group_index] if group_index is not None and group_index < len(groups) else None
        users = await list_users_for_filter(session, stats, "grp", group)
        label = FILTER_LABELS["grp"].format(group=h(group or "—"))
    else:
        filter_code = filter_code if filter_code in FILTER_LABELS else "all"
        users = await list_users_for_filter(session, stats, filter_code)
        label = FILTER_LABELS[filter_code]

    items, page, pages = page_slice(users, page)
    prefix = f"grp.{group_index}" if filter_code == "grp" else filter_code
    await remember(state, students_view=f"{prefix}.{page}")

    text = STUDENTS_TITLE.format(label=label, count=len(users))
    if not users:
        text += f"\n\n{NOTHING_FOUND}"
    if notice:
        text = f"{notice}\n\n{text}"
    rows = [
        [
            button(
                f"{_markers(u, stats[u.id], config)} {short(u.last_name + ' ' + u.first_name, 30)} · {u.group_number}",
                f"st:c:{u.id}",
            )
        ]
        for u in items
    ]
    filters = [[button(title, f"st:v:{code}.0") for title, code in row] for row in FILTER_BUTTONS]
    keyboard = markup(
        *rows,
        pagination_row(page, pages, lambda p: f"st:v:{prefix}.{p}"),
        *filters,
        [button("🎓 Группы", "st:groups:0"), button("🔎 Поиск", "st:search")],
        [button(BACK_BUTTON, "menu:admin")],
    )
    await show_long_screen(state, bot, chat_id, text, keyboard, new=new)


@router.callback_query(F.data.regexp(r"^st:v:[a-z]+(\.\d+){1,2}$"))
async def cb_students(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    await callback.answer()
    await show_students(state, bot, callback.message.chat.id, session, config, callback.data.removeprefix("st:v:"))


@router.callback_query(F.data == "st:back")
async def cb_students_back(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    await callback.answer()
    view = str(await recall(state, "students_view", "all.0"))
    await show_students(state, bot, callback.message.chat.id, session, config, view)


@router.callback_query(F.data.regexp(r"^st:groups:\d+$"))
async def cb_groups(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    groups = await users_repo.list_groups(session)
    items, page, pages = page_slice(groups, _uid(callback))
    offset = page * PAGE_SIZE
    keyboard = markup(
        *[[button(f"🎓 {short(group)}", f"st:v:grp.{offset + i}.0")] for i, group in enumerate(items)],
        pagination_row(page, pages, lambda p: f"st:groups:{p}"),
        [button(BACK_BUTTON, "st:back")],
    )
    await show_screen(state, bot, callback.message.chat.id, GROUPS_TITLE if groups else NOTHING_FOUND, keyboard)
    await callback.answer()


@router.callback_query(F.data == "st:search")
async def cb_search(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(StudentSearch.waiting_query)
    keyboard = markup([button(CANCEL_BUTTON, "st:back")])
    await show_screen(state, bot, callback.message.chat.id, ASK_STUDENT_SEARCH, keyboard)
    await callback.answer()


@router.message(StudentSearch.waiting_query)
async def process_search(message: Message, state: FSMContext, session: AsyncSession, config: Config) -> None:
    keyboard = markup([button(CANCEL_BUTTON, "st:back")])
    query = await read_input(message, state, MAX_NAME_LEN, ASK_STUDENT_SEARCH, keyboard)
    if query is None:
        return
    await remember(state, students_query=query)
    await show_students(state, message.bot, message.chat.id, session, config, "q.0")


# --- Card ---------------------------------------------------------------------------------------------------------


async def show_student_card(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    user_id: int,
    viewer_is_super_admin: bool,
    *,
    notice: str | None = None,
) -> None:
    await state.clear()
    user = await users_repo.get(session, user_id)
    if user is None:
        await show_students(state, bot, chat_id, session, config, notice=ACTION_EXPIRED)
        return

    memberships = await projects_repo.list_user_memberships(session, user.id)
    current = [m for m in memberships if m.end_period is None]
    supplements = await supplements_repo.list_for_student(session, user.id)
    period = current_period(config.timezone)
    recent = supplements[:5]
    periods = {period, period - 1} | {s.period for s in recent if s.status == "approved"}
    payouts = await student_payouts(session, config, user.id, sorted(periods))
    is_super_admin_user = user.telegram_id == config.super_admin_id

    role = "Супер-админ" if is_super_admin_user else ("Администратор" if user.role == "admin" else "Студент")
    lines = [
        f"👤 <b>{h(user.full_name)}</b>" + (" · 🗄 в архиве" if user.is_archived else ""),
        f"🎓 {h(user.group_number)} · 🏷 {role}",
        "",
        "📁 <b>Проекты</b>",
        *[f"• «{h(m.project.name)}» — {membership_span(m, period)}" for m in memberships],
    ]
    if not memberships:
        lines.append("— не участвовал(а)")
    for month in (period, period - 1):
        lines += ["", month_block(month_title(month, period), payouts[month], config)]

    lines.append("")
    counts = {
        status: sum(1 for s in supplements if s.status == status) for status in ("approved", "pending", "rejected")
    }
    lines.append(f"📜 Заявки: ✅ {counts['approved']} · ⏳ {counts['pending']} · ❌ {counts['rejected']}")
    for s in recent:
        line = f"• {KIND_TEXT[s.event.kind]['icon']} «{h(short(s.event.name, 40))}» — {review.status_text(s)}"
        if s.status == "approved" and payouts[s.period].basis_type == "project":
            line += f"\n  {NOT_ADDED_BECAUSE_PROJECT_ADMIN}"
        lines.append(line)
    text = "\n".join(lines)
    if notice:
        text = f"{notice}\n\n{text}"

    active = not user.is_archived
    can_remove = _can_remove(user, viewer_is_super_admin, config)
    keyboard = markup(
        [button("📜 Вся история", f"st:h:{user.id}:0")],
        [button("📁 В проект", f"st:pj:{user.id}:0")]
        + ([button("➖ Из проекта", f"st:pr:{user.id}")] if current else [])
        if active
        else None,
        [button("🏛 Конференция", f"st:aw:{user.id}:c"), button("🎪 Мероприятие", f"st:aw:{user.id}:e")]
        if active
        else None,
        [button("👑 Снять админа" if user.role == "admin" else "👑 Сделать админом", f"st:role:{user.id}")]
        if viewer_is_super_admin and active and not is_super_admin_user
        else None,
        ([button("🗄 В архив", f"st:ar:{user.id}")] if active and can_remove else [])
        + ([button("♻️ Вернуть из архива", f"st:unar:{user.id}")] if not active else [])
        + ([button(DELETE_BUTTON, f"st:del:{user.id}")] if can_remove else []),
        [button("⬅️ К списку", "st:back")],
    )
    await show_long_screen(state, bot, chat_id, text, keyboard)


def _uid(callback: CallbackQuery, index: int = 2) -> int:
    return int(callback.data.split(":")[index])


@router.callback_query(F.data.regexp(r"^st:c:\d+$"))
async def cb_card(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    is_super_admin: bool,
) -> None:
    await callback.answer()
    await show_student_card(state, bot, callback.message.chat.id, session, config, _uid(callback), is_super_admin)


# --- History and award details ------------------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^st:h:\d+:\d+$"))
async def cb_history(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    await state.clear()
    user = await users_repo.get(session, _uid(callback))
    if user is None:
        return
    supplements = await supplements_repo.list_for_student(session, user.id)
    items, page, pages = page_slice(supplements, int(callback.data.split(":")[3]))
    status_icons = {"approved": "✅", "pending": "⏳", "rejected": "❌", "withdrawn": "↩️", "cancelled": "🚫"}
    rows = [
        [
            button(
                f"{status_icons[s.status]}{KIND_TEXT[s.event.kind]['icon']} {short(s.event.name, 28)} · "
                + (format_period(s.period) if s.period is not None else f"{s.event.held_on:%d.%m.%y}"),
                f"st:a:{s.id}",
            )
        ]
        for s in items
    ]
    text = STUDENT_HISTORY_TITLE.format(name=h(user.full_name))
    if not supplements:
        text += f"\n\n{STUDENT_HISTORY_EMPTY}"
    keyboard = markup(
        *rows,
        pagination_row(page, pages, lambda p: f"st:h:{user.id}:{p}"),
        [button("⬅️ К карточке", f"st:c:{user.id}")],
    )
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)


async def show_award(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    supplement: Supplement,
    notice: str | None = None,
) -> None:
    await state.clear()
    lines = [review.request_card_text(supplement, config), "", review.status_text(supplement)]
    if supplement.status == "approved":
        payout = (await student_payouts(session, config, supplement.student_id, [supplement.period]))[supplement.period]
        if payout.basis_type == "project":
            lines.append(NOT_ADDED_BECAUSE_PROJECT_ADMIN)
    text = "\n".join(lines + review.decision_lines(supplement, config))
    if notice:
        text = f"{notice}\n\n{text}"
    keyboard = markup(
        [button("📥 Рассмотреть", f"rq:o:{supplement.id}")] if supplement.status == "pending" else None,
        [button("✏️ Изменить сумму", f"st:ac:{supplement.id}"), button("🚫 Отменить", f"st:ax:{supplement.id}")]
        if supplement.status == "approved"
        else None,
        [button("⬅️ К истории", f"st:h:{supplement.student_id}:0")],
    )
    await show_screen(state, bot, chat_id, text, keyboard)


async def _supplement_or_alert(callback: CallbackQuery, session: AsyncSession) -> Supplement | None:
    supplement = await supplements_repo.get(session, _uid(callback))
    if supplement is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
    return supplement


@router.callback_query(F.data.regexp(r"^st:a:\d+$"))
async def cb_award(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config) -> None:
    supplement = await _supplement_or_alert(callback, session)
    if supplement is None:
        return
    await callback.answer()
    await show_award(state, bot, callback.message.chat.id, session, config, supplement)


@router.callback_query(F.data.regexp(r"^st:ac:\d+$"))
async def cb_change_amount(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    supplement = await _supplement_or_alert(callback, session)
    if supplement is None:
        return
    keyboard = markup(
        amount_row(lambda amount: f"st:aca:{supplement.id}:{amount}"),
        [button(BACK_BUTTON, f"st:a:{supplement.id}")],
    )
    await show_screen(state, bot, callback.message.chat.id, PICK_NEW_AMOUNT, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^st:aca:\d+:[\d.]+$"))
async def cb_change_amount_apply(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    amount = parse_amount(callback.data.split(":")[3])
    if amount is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    ok = await review.change_award_amount(bot, session, _uid(callback), amount)
    supplement = await supplements_repo.get(session, _uid(callback))
    notice = AMOUNT_CHANGED.format(amount=money(amount)) if ok else CARD_ALREADY_PROCESSED_ALERT
    await show_award(state, bot, callback.message.chat.id, session, config, supplement, notice)


@router.callback_query(F.data.regexp(r"^st:ax:\d+$"))
async def cb_cancel_award(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    supplement_id = _uid(callback)
    await state.clear()
    await state.set_state(AdminCancelAward.waiting_reason)
    await state.update_data(supplement_id=supplement_id)
    keyboard = markup([button(SKIP_BUTTON, "st:axs"), button(BACK_BUTTON, f"st:a:{supplement_id}")])
    await show_screen(state, bot, callback.message.chat.id, ASK_CANCEL_REASON, keyboard)
    await callback.answer()


async def _finish_cancel(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    config: Config,
    admin: User,
    data: dict,
    reason: str | None,
) -> None:
    ok = await review.cancel_award(bot, session, data["supplement_id"], admin, reason)
    supplement = await supplements_repo.get(session, data["supplement_id"])
    await show_award(
        state, bot, chat_id, session, config, supplement, CANCEL_DONE if ok else CARD_ALREADY_PROCESSED_ALERT
    )


@router.callback_query(AdminCancelAward.waiting_reason, F.data == "st:axs")
async def cb_cancel_award_skip(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, current_user: User
) -> None:
    data = await take_state_data(state, AdminCancelAward.waiting_reason)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await _finish_cancel(state, bot, callback.message.chat.id, session, config, current_user, data, None)


@router.message(AdminCancelAward.waiting_reason)
async def process_cancel_reason(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, current_user: User
) -> None:
    supplement_id = (await state.get_data()).get("supplement_id")
    keyboard = markup([button(SKIP_BUTTON, "st:axs"), button(BACK_BUTTON, f"st:a:{supplement_id}")])
    reason = await read_input(message, state, MAX_DESCRIPTION_LEN, ASK_CANCEL_REASON, keyboard)
    if reason is None:
        return
    data = await take_state_data(state, AdminCancelAward.waiting_reason)
    if data is not None:
        await _finish_cancel(state, bot, message.chat.id, session, config, current_user, data, reason)


# --- Projects -----------------------------------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^st:pj:\d+:\d+$"))
async def cb_pick_project(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    user = await users_repo.get(session, _uid(callback))
    if user is None:
        return
    projects = await projects_repo.list_all(session, include_archived=False)
    items, page, pages = page_slice(projects, int(callback.data.split(":")[3]))
    text = PICK_PROJECT_FOR_STUDENT.format(name=h(user.full_name)) if projects else NO_PROJECTS
    keyboard = markup(
        *[[button(f"📁 {short(p.name)}", f"st:pjs:{user.id}:{p.id}")] for p in items],
        pagination_row(page, pages, lambda p: f"st:pj:{user.id}:{p}"),
        [button(BACK_BUTTON, f"st:c:{user.id}")],
    )
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)


async def add_to_project(
    bot: Bot, session: AsyncSession, config: Config, user: User, project_id: int, admin: User
) -> str:
    """Add a member from the current month and notify them. Returns the notice for the admin."""
    project = await projects_repo.get(session, project_id)
    if project is None or project.is_archived:
        return ACTION_EXPIRED
    period = current_period(config.timezone)
    member = await projects_repo.add_member(session, project.id, user.id, period, admin.id)
    if member is None:
        return PROJECT_MEMBER_EXISTS.format(name=h(user.full_name), project=h(project.name))
    amount = money(config.project_amount)
    text = STUDENT_NOTIFY_PROJECT_ADDED.format(name=h(project.name), amount=amount, period=format_period(period))
    await review.notify(bot, user.telegram_id, text)
    return PROJECT_MEMBER_ADDED.format(
        name=h(user.full_name), project=h(project.name), amount=amount, period=format_period(period)
    )


async def end_project_membership(
    bot: Bot, session: AsyncSession, config: Config, member: ProjectMember, admin: User
) -> str:
    if not await projects_repo.end_membership(session, member, current_period(config.timezone), admin.id):
        return ACTION_EXPIRED
    paid = paid_until_text(member)
    text = STUDENT_NOTIFY_PROJECT_REMOVED.format(name=h(member.project.name), paid=paid)
    await review.notify(bot, member.user.telegram_id, text)
    return MEMBERSHIP_ENDED.format(name=h(member.user.full_name), project=h(member.project.name), paid=paid)


@router.callback_query(F.data.regexp(r"^st:pjs:\d+:\d+$"))
async def cb_add_to_project(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    await callback.answer()
    user = await users_repo.get(session, _uid(callback))
    if user is None or user.is_archived:
        return
    notice = await add_to_project(bot, session, config, user, int(callback.data.split(":")[3]), current_user)
    await show_student_card(
        state, bot, callback.message.chat.id, session, config, user.id, is_super_admin, notice=notice
    )


@router.callback_query(F.data.regexp(r"^st:pr:\d+$"))
async def cb_pick_membership(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    user = await users_repo.get(session, _uid(callback))
    if user is None:
        return
    current = [m for m in await projects_repo.list_user_memberships(session, user.id) if m.end_period is None]
    keyboard = markup(
        *[[button(f"➖ {short(m.project.name)}", f"st:prs:{m.id}")] for m in current],
        [button(BACK_BUTTON, f"st:c:{user.id}")],
    )
    await show_screen(
        state, bot, callback.message.chat.id, PICK_MEMBERSHIP_TO_END.format(name=h(user.full_name)), keyboard
    )


@router.callback_query(F.data.regexp(r"^st:prs:\d+$"))
async def cb_confirm_end_membership(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    member = await projects_repo.get_member(session, _uid(callback))
    if member is None or member.end_period is not None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    period = current_period(config.timezone)
    text = CONFIRM_END_MEMBERSHIP.format(
        name=h(member.user.full_name),
        project=h(member.project.name),
        span=membership_span(member, period),
        period=format_period(period),
    )
    keyboard = markup([button("➖ Да, убрать", f"st:pry:{member.id}"), button(BACK_BUTTON, f"st:c:{member.user_id}")])
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^st:pry:\d+$"))
async def cb_end_membership(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    await callback.answer()
    member = await projects_repo.get_member(session, _uid(callback))
    if member is None:
        return
    notice = await end_project_membership(bot, session, config, member, current_user)
    await show_student_card(
        state, bot, callback.message.chat.id, session, config, member.user_id, is_super_admin, notice=notice
    )


# --- Award from the card ------------------------------------------------------------------------------------------


async def _show_award_picker(
    state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession, page: int, notice: str | None = None
) -> None:
    data = await state.get_data()
    user = await users_repo.get(session, data["user_id"])
    events = await events_repo.list_for_kind(session, data["kind"], verified_only=False)
    if data.get("query"):
        events = events_repo.search(events, data["query"])
    items, page, pages = page_slice(events, page)
    words = KIND_TEXT[data["kind"]]
    text = AWARD_PICK_EVENT.format(icon=words["icon"], acc=words["acc"], name=h(user.full_name))
    if data.get("query"):
        text = f"🔎 «{h(data['query'])}»{'' if events else ' — ' + NOTHING_FOUND}\n\n{text}"
    if notice:
        text = f"{notice}\n\n{text}"
    await state.set_state(AdminAward.choosing_event)
    await show_screen(state, bot, chat_id, text, event_picker_keyboard("aw", items, page, pages, f"st:c:{user.id}"))


def _cancel_to_card(data: dict):
    return markup([button(CANCEL_BUTTON, f"st:c:{data['user_id']}")])


@router.callback_query(F.data.regexp(r"^st:aw:\d+:[ce]$"))
async def cb_award_start(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    await state.update_data(user_id=_uid(callback), kind=KIND_BY_CODE[callback.data[-1]])
    await _show_award_picker(state, bot, callback.message.chat.id, session, 0)
    await callback.answer()


@router.callback_query(AdminAward.choosing_event, F.data.regexp(r"^aw:l:\d+$"))
async def cb_award_page(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _show_award_picker(state, bot, callback.message.chat.id, session, _uid(callback))
    await callback.answer()


@router.callback_query(AdminAward.choosing_event, F.data == "aw:q")
async def cb_award_search(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminAward.searching_event)
    await show_screen(state, bot, callback.message.chat.id, ASK_EVENT_SEARCH, _cancel_to_card(await state.get_data()))
    await callback.answer()


@router.message(AdminAward.searching_event)
async def process_award_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    query = await read_input(message, state, MAX_TITLE_LEN, ASK_EVENT_SEARCH, _cancel_to_card(await state.get_data()))
    if query is None:
        return
    await state.update_data(query=query)
    await _show_award_picker(state, message.bot, message.chat.id, session, 0)


@router.callback_query(AdminAward.choosing_event, F.data.regexp(r"^aw:e:\d+$"))
async def cb_award_pick(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await callback.answer()
    data = await state.get_data()
    event = await events_repo.get(session, _uid(callback))
    if event is None or event.kind != data["kind"]:
        await _show_award_picker(state, bot, callback.message.chat.id, session, 0, notice=ACTION_EXPIRED)
        return
    if await supplements_repo.has_open_request(session, data["user_id"], event.id):
        notice = SUBMISSION_DUPLICATE.format(name=h(event.name))
        await _show_award_picker(state, bot, callback.message.chat.id, session, 0, notice=notice)
        return
    await state.update_data(event_id=event.id)
    await _ask_award_details(state, bot, callback.message.chat.id, session)


@router.callback_query(AdminAward.choosing_event, F.data == "aw:new")
async def cb_award_new_event(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.set_state(AdminAward.waiting_new_event_name)
    text = ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[data["kind"]]["gen"])
    await show_screen(state, bot, callback.message.chat.id, text, _cancel_to_card(data))
    await callback.answer()


@router.message(AdminAward.waiting_new_event_name)
async def process_award_new_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt = ASK_NEW_EVENT_NAME.format(gen=KIND_TEXT[data["kind"]]["gen"])
    name = await read_input(message, state, MAX_TITLE_LEN, prompt, _cancel_to_card(data))
    if name is None:
        return
    await state.update_data(new_event_name=name)
    await state.set_state(AdminAward.waiting_new_event_date)
    await show_screen(state, message.bot, message.chat.id, ASK_NEW_EVENT_DATE, _cancel_to_card(data))


@router.message(AdminAward.waiting_new_event_date)
async def process_award_new_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    raw = await read_input(message, state, 20, ASK_NEW_EVENT_DATE, _cancel_to_card(data))
    if raw is None:
        return
    held_on = parse_date(raw)
    if held_on is None:
        text = f"{INVALID_DATE}\n\n{ASK_NEW_EVENT_DATE}"
        await show_screen(state, message.bot, message.chat.id, text, _cancel_to_card(data))
        return
    await state.update_data(new_event_date=held_on.isoformat(), event_id=None)
    await _ask_award_details(state, message.bot, message.chat.id, session)


async def _ask_award_details(state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.set_state(AdminAward.waiting_details)
    rows = []
    if data["kind"] == "conference":
        memberships = await projects_repo.list_user_memberships(session, data["user_id"])
        options = [m.project.name for m in memberships if m.end_period is None]
        await state.update_data(project_options=options)
        rows = [[button(f"📁 {short(name)}", f"aw:p:{i}")] for i, name in enumerate(options)]
    text = AWARD_ASK_PROJECT if data["kind"] == "conference" else AWARD_ASK_WHAT_DID
    keyboard = markup(*rows, [button(SKIP_BUTTON, "aw:p:-"), button(CANCEL_BUTTON, f"st:c:{data['user_id']}")])
    await show_screen(state, bot, chat_id, text, keyboard)


async def _ask_amount(state: FSMContext, bot: Bot, chat_id: int, session: AsyncSession) -> None:
    data = await state.get_data()
    user = await users_repo.get(session, data["user_id"])
    await state.set_state(AdminAward.choosing_amount)
    keyboard = markup(amount_row(lambda amount: f"aw:m:{amount}"), [button(CANCEL_BUTTON, f"st:c:{data['user_id']}")])
    await show_screen(state, bot, chat_id, AWARD_PICK_AMOUNT.format(name=h(user.full_name)), keyboard)


@router.callback_query(AdminAward.waiting_details, F.data.regexp(r"^aw:p:(\d+|-)$"))
async def cb_award_detail_option(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    data = await state.get_data()
    choice = callback.data.split(":")[2]
    if choice != "-":
        options = data.get("project_options", [])
        if int(choice) >= len(options):
            await callback.answer(ACTION_EXPIRED, show_alert=True)
            return
        await state.update_data(project_name=options[int(choice)])
    await _ask_amount(state, bot, callback.message.chat.id, session)
    await callback.answer()


@router.message(AdminAward.waiting_details)
async def process_award_details(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    conference = data["kind"] == "conference"
    prompt = AWARD_ASK_PROJECT if conference else AWARD_ASK_WHAT_DID
    keyboard = markup([button(SKIP_BUTTON, "aw:p:-"), button(CANCEL_BUTTON, f"st:c:{data['user_id']}")])
    value = await read_input(message, state, MAX_TITLE_LEN if conference else MAX_DESCRIPTION_LEN, prompt, keyboard)
    if value is None:
        return
    await state.update_data(**{"project_name" if conference else "what_did": value})
    await _ask_amount(state, message.bot, message.chat.id, session)


@router.callback_query(AdminAward.choosing_amount, F.data.regexp(r"^aw:m:[\d.]+$"))
async def cb_award_amount(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config
) -> None:
    amount = parse_amount(callback.data.split(":")[2])
    if amount is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(amount=str(amount))
    data = await state.get_data()
    user = await users_repo.get(session, data["user_id"])
    if data.get("event_id"):
        event = await events_repo.get(session, data["event_id"])
        line = review.event_line(event.kind, event.name, event.held_on, verified=event.is_verified)
    else:
        line = review.event_line(data["kind"], data["new_event_name"], dt.date.fromisoformat(data["new_event_date"]))
    text = AWARD_CONFIRM.format(
        amount=money(amount),
        student=h(user.full_name),
        event_line=line,
        details=review.details_line(data["kind"], data.get("project_name"), data.get("what_did")),
        period=period_title(current_period(config.timezone)),
    )
    await state.set_state(AdminAward.confirm)
    keyboard = markup([button(CONFIRM_BUTTON, "aw:y"), button(CANCEL_BUTTON, f"st:c:{data['user_id']}")])
    await show_screen(state, bot, callback.message.chat.id, text, keyboard)


@router.callback_query(AdminAward.confirm, F.data == "aw:y")
async def cb_award_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    data = await take_state_data(state, AdminAward.confirm)
    if data is None:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    chat_id = callback.message.chat.id
    user = await users_repo.get(session, data["user_id"])
    amount = parse_amount(data["amount"])
    if user is None or user.is_archived:
        await show_students(state, bot, chat_id, session, config, notice=ACTION_EXPIRED)
        return

    if data.get("event_id"):
        event = await events_repo.get(session, data["event_id"])
        if await supplements_repo.has_open_request(session, user.id, event.id):
            notice = SUBMISSION_DUPLICATE.format(name=h(event.name))
            await show_student_card(state, bot, chat_id, session, config, user.id, is_super_admin, notice=notice)
            return
        if not event.is_verified:
            await events_repo.update_fields(session, event, is_verified=True)
    else:
        held_on = dt.date.fromisoformat(data["new_event_date"])
        event = await events_repo.create(
            session, data["kind"], data["new_event_name"], held_on, current_user.id, verified=True
        )

    award = await supplements_repo.create_award(
        session,
        user.id,
        event.id,
        project_name=data.get("project_name"),
        what_did=data.get("what_did"),
        amount=amount,
        period=current_period(config.timezone),
        admin_id=current_user.id,
        admin_name=current_user.full_name,
    )
    if award is None:
        notice = SUBMISSION_DUPLICATE.format(name=h(event.name))
        await show_student_card(state, bot, chat_id, session, config, user.id, is_super_admin, notice=notice)
        return
    text = STUDENT_NOTIFY_AWARD.format(amount=money(amount), title=h(event.name))
    text += await review.payout_note(session, config, user.id, award.period)
    await review.notify(bot, user.telegram_id, text)
    notice = AWARD_DONE.format(amount=money(amount), event=h(event.name))
    await show_student_card(state, bot, chat_id, session, config, user.id, is_super_admin, notice=notice)


# --- Role and archive ---------------------------------------------------------------------------------------------


@router.callback_query(F.data.regexp(r"^st:role:\d+$"))
async def cb_role_ask(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if not is_super_admin or user is None or user.telegram_id == config.super_admin_id:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    template = ROLE_CONFIRM_DEMOTE if user.role == "admin" else ROLE_CONFIRM_PROMOTE
    keyboard = markup([button(CONFIRM_BUTTON, f"st:roley:{user.id}"), button(BACK_BUTTON, f"st:c:{user.id}")])
    await show_screen(state, bot, callback.message.chat.id, template.format(name=h(user.full_name)), keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^st:roley:\d+$"))
async def cb_role_apply(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if not is_super_admin or user is None or user.is_archived or user.telegram_id == config.super_admin_id:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    promote = user.role != "admin"
    await users_repo.set_role(session, user, "admin" if promote else "student")
    await sync_role_commands(bot, user.telegram_id, is_admin=promote, config=config)
    notice = (ROLE_PROMOTED if promote else ROLE_DEMOTED).format(name=h(user.full_name))
    await show_student_card(
        state, bot, callback.message.chat.id, session, config, user.id, is_super_admin, notice=notice
    )


@router.callback_query(F.data.regexp(r"^st:ar:\d+$"))
async def cb_archive_ask(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if user is None or user.is_archived or not _can_remove(user, is_super_admin, config):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    keyboard = markup([button("🗄 Да, в архив", f"st:ary:{user.id}"), button(BACK_BUTTON, f"st:c:{user.id}")])
    await show_screen(state, bot, callback.message.chat.id, ARCHIVE_CONFIRM.format(name=h(user.full_name)), keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^st:ary:\d+$"))
async def cb_archive(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    config: Config,
    current_user: User,
    is_super_admin: bool,
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if user is None or user.is_archived or not _can_remove(user, is_super_admin, config):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    period = current_period(config.timezone)
    await projects_repo.end_all_for_user(session, user.id, period, current_user.id)
    for supplement in await supplements_repo.list_pending_for_student(session, user.id):
        await review.withdraw_request(bot, session, config, supplement.id, student_archived=True)
    was_admin = user.role == "admin"
    await users_repo.set_archived(session, user, True)
    if was_admin:
        await sync_role_commands(bot, user.telegram_id, is_admin=False, config=config)
    notice = ARCHIVED_DONE.format(name=h(user.full_name))
    await show_student_card(
        state, bot, callback.message.chat.id, session, config, user.id, is_super_admin, notice=notice
    )


@router.callback_query(F.data.regexp(r"^st:unar:\d+$"))
async def cb_unarchive(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if user is None or not user.is_archived:
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    await users_repo.set_archived(session, user, False)
    notice = UNARCHIVED_DONE.format(name=h(user.full_name))
    await show_student_card(
        state, bot, callback.message.chat.id, session, config, user.id, is_super_admin, notice=notice
    )


@router.callback_query(F.data.regexp(r"^st:del:\d+$"))
async def cb_delete_ask(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if user is None or not _can_remove(user, is_super_admin, config):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    impact = await deletion_repo.user_impact(session, user)
    text = DELETE_STUDENT_CONFIRM.format(
        name=h(user.full_name),
        supplements=impact.supplements,
        approved=impact.approved,
        memberships=impact.memberships,
    )
    if user.role == "admin":
        text += DELETE_ADMIN_NOTE
    keyboard = markup([button(DELETE_CONFIRM_BUTTON, f"st:dely:{user.id}")], [button(BACK_BUTTON, f"st:c:{user.id}")])
    await show_screen(state, bot, callback.message.chat.id, text + DELETE_UNDO_NOTE, keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^st:dely:\d+$"))
async def cb_delete(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, config: Config, is_super_admin: bool
) -> None:
    user = await users_repo.get(session, _uid(callback))
    if user is None or not _can_remove(user, is_super_admin, config):
        await callback.answer(ACTION_EXPIRED, show_alert=True)
        return
    await callback.answer()
    impact = await deletion_repo.user_impact(session, user)
    await review.stamp_deleted_requests(bot, session, config, impact.pending_ids)
    name, telegram_id, was_admin = user.full_name, user.telegram_id, user.role == "admin"
    await deletion_repo.delete_user(session, user)
    if was_admin:
        await sync_role_commands(bot, telegram_id, is_admin=False, config=config)
    view = str(await recall(state, "students_view", "all.0"))
    notice = STUDENT_DELETED.format(name=h(name))
    await show_students(state, bot, callback.message.chat.id, session, config, view, notice=notice)
