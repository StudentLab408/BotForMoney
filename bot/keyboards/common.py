from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать заявку", callback_data="menu:submit")
    builder.button(text="👤 Мой профиль", callback_data="menu:profile")
    if is_admin:
        builder.button(text="🛠 Админ-панель", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В главное меню", callback_data="menu:main")
    return builder.as_markup()
