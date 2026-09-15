"""The catalog picker shared by the student request form (prefix "sb") and the admin award form (prefix "aw")."""

from aiogram.types import InlineKeyboardMarkup

from bot.db.models import Event
from bot.keyboards.builders import button, markup, pagination_row, short
from bot.utils.texts import ADD_NEW_BUTTON, CANCEL_BUTTON, PARTICIPATION_TEXT, SEARCH_BUTTON


def event_button_text(event: Event) -> str:
    marks = ("🗄 " if event.is_archived else "") + ("❔ " if not event.is_verified else "")
    return f"{marks}{short(event.name, 32)} · {event.held_on:%d.%m.%y}"


def event_picker_keyboard(
    prefix: str, events: list[Event], page: int, pages: int, cancel_cb: str
) -> InlineKeyboardMarkup:
    return markup(
        *[[button(event_button_text(e), f"{prefix}:e:{e.id}")] for e in events],
        pagination_row(page, pages, lambda p: f"{prefix}:l:{p}"),
        [button(SEARCH_BUTTON, f"{prefix}:q"), button(ADD_NEW_BUTTON, f"{prefix}:new")],
        [button(CANCEL_BUTTON, cancel_cb)],
    )


def participation_row(prefix: str) -> list:
    """📄 Статья / 📝 Тезисы / 📁 Проект — how the student took part in a conference."""
    return [
        button(f"{words['icon']} {words['label']}", f"{prefix}:w:{participation}")
        for participation, words in PARTICIPATION_TEXT.items()
    ]
