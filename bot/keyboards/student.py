from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import CANCEL_BUTTON, CONFIRM_BUTTON, MAIN_MENU_BUTTON, RETRY_BUTTON


def submission_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏛 Конференция", callback_data="submit_type:conference")
    builder.button(text="🎪 Мероприятие", callback_data="submit_type:event")
    builder.button(text=CANCEL_BUTTON, callback_data="flow:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_cancel_keyboard(confirm_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data=confirm_cb)
    builder.button(text=CANCEL_BUTTON, callback_data="flow:cancel")
    builder.adjust(2)
    return builder.as_markup()


def registration_confirm_keyboard(can_cancel: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data="reg:confirm")
    builder.button(text=RETRY_BUTTON, callback_data="reg:retry")
    if can_cancel:
        builder.button(text=CANCEL_BUTTON, callback_data="flow:cancel")
    builder.adjust(1)
    return builder.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить данные", callback_data="profile:edit")
    builder.button(text=MAIN_MENU_BUTTON, callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
