from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import CANCEL_BUTTON, MAIN_MENU_BUTTON


def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать заявку", callback_data="menu:submit")
    builder.button(text="📜 Мои заявки", callback_data="menu:my_submissions")
    builder.button(text="💰 Мои начисления", callback_data="menu:payouts")
    builder.button(text="👤 Мой профиль", callback_data="menu:profile")
    if is_admin:
        builder.button(text="🛠 Админ-панель", callback_data="menu:admin")
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=MAIN_MENU_BUTTON, callback_data="menu:main")
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CANCEL_BUTTON, callback_data="flow:cancel")
    return builder.as_markup()
