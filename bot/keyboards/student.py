from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.builders import button, markup
from bot.utils.texts import CANCEL_BUTTON, CONFIRM_BUTTON, MAIN_MENU_BUTTON, RETRY_BUTTON


def submission_type_keyboard() -> InlineKeyboardMarkup:
    return markup(
        [button("🏛 Конференция", "sb:k:c"), button("🎪 Мероприятие", "sb:k:e")],
        [button(CANCEL_BUTTON, "flow:cancel")],
    )


def confirm_cancel_keyboard(confirm_cb: str, cancel_cb: str = "flow:cancel") -> InlineKeyboardMarkup:
    return markup([button(CONFIRM_BUTTON, confirm_cb), button(CANCEL_BUTTON, cancel_cb)])


def registration_confirm_keyboard(can_cancel: bool) -> InlineKeyboardMarkup:
    return markup(
        [button(CONFIRM_BUTTON, "reg:confirm")],
        [button(RETRY_BUTTON, "reg:retry")],
        [button(CANCEL_BUTTON, "flow:cancel")] if can_cancel else None,
    )


def profile_keyboard() -> InlineKeyboardMarkup:
    return markup([button("✏️ Изменить данные", "profile:edit")], [button(MAIN_MENU_BUTTON, "menu:main")])
