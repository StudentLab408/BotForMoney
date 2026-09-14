from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS
from bot.db.models import User
from bot.utils.texts import BACK_BUTTON, CANCEL_BUTTON, CONFIRM_BUTTON, SKIP_BUTTON


def admin_menu_keyboard(is_super_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Начислить проектную надбавку", callback_data="admin:project_entry")
    builder.button(text="📊 Отчёт за месяц", callback_data="admin:report")
    builder.button(text="📄 Сформировать список", callback_data="admin:export")
    builder.button(text="👥 Активность студентов", callback_data="admin:activity")
    if is_super_admin:
        builder.button(text="👑 Управление админами", callback_data="admin:manage_admins")
    builder.button(text="⬅️ В главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def approval_keyboard(supplement_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in ALLOWED_CONF_EVENT_AMOUNTS:
        builder.button(text=f"✅ {amount} BYN", callback_data=f"sup:approve:{supplement_id}:{amount}")
    builder.button(text="❌ Отклонить", callback_data=f"sup:reject:{supplement_id}")
    builder.adjust(3, 1)
    return builder.as_markup()


def reject_reason_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=SKIP_BUTTON, callback_data="reject:skip")
    return builder.as_markup()


def student_search_results_keyboard(students: list[User]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in students:
        builder.button(
            text=f"{s.last_name} {s.first_name} ({s.group_number})",
            callback_data=f"admin:pick_student:{s.id}",
        )
    builder.button(text=CANCEL_BUTTON, callback_data="admin:cancel_project_entry")
    builder.adjust(1)
    return builder.as_markup()


def project_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data="admin:project_confirm")
    builder.button(text=CANCEL_BUTTON, callback_data="admin:cancel_project_entry")
    builder.adjust(2)
    return builder.as_markup()


def promote_confirm_keyboard(target_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data=f"admin:promote_confirm:{target_id}")
    builder.button(text=CANCEL_BUTTON, callback_data="admin:promote_cancel")
    builder.adjust(2)
    return builder.as_markup()


def admin_list_keyboard(admins: list[User]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in admins:
        builder.button(text=f"➖ {a.last_name} {a.first_name}", callback_data=f"admin:demote:{a.id}")
    builder.button(text="➕ Назначить админа", callback_data="admin:promote_start")
    builder.button(text=BACK_BUTTON, callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def month_picker_keyboard(purpose: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Текущий месяц", callback_data=f"month:{purpose}:current")
    builder.button(text="📅 Прошлый месяц", callback_data=f"month:{purpose}:previous")
    builder.button(text="⌨️ Другой месяц", callback_data=f"month:{purpose}:custom")
    builder.button(text=BACK_BUTTON, callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BACK_BUTTON, callback_data="menu:admin")
    return builder.as_markup()
