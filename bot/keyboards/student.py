from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import CANCEL_BUTTON, CONFIRM_BUTTON, RETRY_BUTTON


def submission_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏛 Конференция", callback_data="submit_type:conference")
    builder.button(text="🎪 Мероприятие", callback_data="submit_type:event")
    builder.button(text=CANCEL_BUTTON, callback_data="submit:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_cancel_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data=confirm_cb)
    builder.button(text=CANCEL_BUTTON, callback_data=cancel_cb)
    builder.adjust(2)
    return builder.as_markup()


def registration_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=CONFIRM_BUTTON, callback_data="reg:confirm")
    builder.button(text=RETRY_BUTTON, callback_data="reg:retry")
    builder.adjust(1)
    return builder.as_markup()
