from aiogram.types import InlineKeyboardMarkup

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS
from bot.keyboards.builders import button, markup
from bot.utils.format import money
from bot.utils.texts import BACK_BUTTON, MAIN_MENU_BUTTON


def admin_menu_keyboard(is_super_admin: bool, pending_count: int) -> InlineKeyboardMarkup:
    return markup(
        [button(f"📥 Заявки ({pending_count})", "rq:l:0")],
        [button("👥 Студенты", "st:v:all.0")],
        [button("📁 Проекты", "pj:l:0")],
        [button("🏛 Конференции", "ev:l:c:0"), button("🎪 Мероприятия", "ev:l:e:0")],
        [button("📊 Отчёт", "admin:report"), button("📄 Списки", "admin:export")],
        [button("👑 Администраторы", "admin:manage_admins")] if is_super_admin else None,
        [button(MAIN_MENU_BUTTON, "menu:main")],
    )


def amount_row(callback_for) -> list:
    """One button per allowed amount; callback_for receives the amount as a plain string like '12.5'."""
    return [button(f"✅ {money(amount)} BYN", callback_for(str(amount))) for amount in ALLOWED_CONF_EVENT_AMOUNTS]


def month_picker_keyboard(purpose: str) -> InlineKeyboardMarkup:
    return markup(
        [button("📅 Текущий месяц", f"month:{purpose}:current")],
        [button("📅 Прошлый месяц", f"month:{purpose}:previous")],
        [button("⌨️ Другой месяц", f"month:{purpose}:custom")],
        [button(BACK_BUTTON, "menu:admin")],
    )


def back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    return markup([button(BACK_BUTTON, "menu:admin")])
