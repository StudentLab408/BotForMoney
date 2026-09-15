from collections.abc import Callable, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PAGE_SIZE = 8


def button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def markup(*rows: Sequence[InlineKeyboardButton] | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(row) for row in rows if row])


def short(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def page_slice[T](items: Sequence[T], page: int, page_size: int = PAGE_SIZE) -> tuple[list[T], int, int]:
    """Items of one page, the page clamped into range, and the total number of pages."""
    pages = max(1, -(-len(items) // page_size))
    page = min(max(page, 0), pages - 1)
    return list(items[page * page_size : (page + 1) * page_size]), page, pages


def pagination_row(page: int, pages: int, callback_for: Callable[[int], str]) -> list[InlineKeyboardButton]:
    if pages <= 1:
        return []
    return [
        button("◀️", callback_for(page - 1 if page > 0 else pages - 1)),
        button(f"{page + 1}/{pages}", "noop"),
        button("▶️", callback_for(page + 1 if page < pages - 1 else 0)),
    ]
