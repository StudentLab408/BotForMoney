from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import InlineKeyboardMarkup, Message

from bot.utils.screen import delete_message, show_screen
from bot.utils.texts import INPUT_NOT_TEXT, INPUT_TOO_LONG

MAX_NAME_LEN = 100
MAX_GROUP_LEN = 50
MAX_TITLE_LEN = 300
MAX_DESCRIPTION_LEN = 1000


def validate_text(raw: str | None, max_len: int) -> tuple[str | None, str | None]:
    """Return (value, None) for usable input, or (None, error_text)."""
    text = (raw or "").strip()
    if not text or text.startswith("/"):
        return None, INPUT_NOT_TEXT
    if len(text) > max_len:
        return None, INPUT_TOO_LONG.format(max_len=max_len)
    return text, None


async def read_input(
    message: Message,
    state: FSMContext,
    max_len: int,
    prompt: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> str | None:
    """Consume a form answer: delete the user's message; on bad input re-render the prompt with the error."""
    await delete_message(message.bot, message.chat.id, message.message_id)
    value, error = validate_text(message.text, max_len)
    if error is not None:
        await show_screen(state, message.bot, message.chat.id, f"{error}\n\n{prompt}", reply_markup)
    return value


async def take_state_data(state: FSMContext, expected: State) -> dict[str, Any] | None:
    """Consume FSM data of a confirm step exactly once, so a double tap cannot act twice.

    Safe because the dispatcher uses SimpleEventIsolation: updates from one user are handled one at a time.
    """
    if await state.get_state() != expected.state:
        return None
    data = await state.get_data()
    await state.clear()
    return data
