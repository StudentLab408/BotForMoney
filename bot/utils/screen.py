"""Single-window UI: each chat has one "screen" message that is edited in place instead of piling up."""

import logging
from contextlib import suppress
from dataclasses import replace

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from bot.utils.format import split_message

logger = logging.getLogger(__name__)


def _ui_context(state: FSMContext) -> FSMContext:
    # Separate namespace, so state.clear() in form flows doesn't forget the screen message.
    return FSMContext(storage=state.storage, key=replace(state.key, destiny="ui"))


async def delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    # Already deleted or older than 48h — nothing useful to do.
    with suppress(TelegramAPIError):
        await bot.delete_message(chat_id, message_id)


async def _drop_extras(bot: Bot, chat_id: int, data: dict) -> None:
    for message_id in data.get("extra_ids", []):
        await delete_message(bot, chat_id, message_id)


async def show_screen(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    new: bool = False,
) -> None:
    """Render the chat's screen. new=True re-sends it at the bottom (e.g. after a command or files)."""
    ui = _ui_context(state)
    data = await ui.get_data()
    screen_id: int | None = data.get("screen_id")
    await _drop_extras(bot, chat_id, data)

    if screen_id is not None and not new:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=screen_id, reply_markup=reply_markup)
            await ui.set_data({"screen_id": screen_id})
            return
        except TelegramBadRequest as error:
            if "message is not modified" in str(error):
                await ui.set_data({"screen_id": screen_id})
                return
            logger.debug("Screen %s not editable, re-sending: %s", screen_id, error)

    if screen_id is not None:
        await delete_message(bot, chat_id, screen_id)
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    await ui.set_data({"screen_id": sent.message_id})


async def show_long_screen(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    new: bool = False,
) -> None:
    """Like show_screen, but text over the Telegram limit is split; extra parts are cleaned up later."""
    chunks = split_message(text)
    if len(chunks) == 1:
        await show_screen(state, bot, chat_id, text, reply_markup, new=new)
        return

    ui = _ui_context(state)
    data = await ui.get_data()
    await _drop_extras(bot, chat_id, data)
    if data.get("screen_id") is not None:
        await delete_message(bot, chat_id, data["screen_id"])

    extra_ids = [(await bot.send_message(chat_id, chunk)).message_id for chunk in chunks[:-1]]
    sent = await bot.send_message(chat_id, chunks[-1], reply_markup=reply_markup)
    await ui.set_data({"screen_id": sent.message_id, "extra_ids": extra_ids})


async def adopt_screen(state: FSMContext, bot: Bot, chat_id: int, message_id: int) -> None:
    """Make the message the user interacted with the screen, removing any other screen."""
    ui = _ui_context(state)
    data = await ui.get_data()
    if data.get("screen_id") == message_id:
        return
    await _drop_extras(bot, chat_id, data)
    if data.get("screen_id") is not None:
        await delete_message(bot, chat_id, data["screen_id"])
    await ui.set_data({"screen_id": message_id})
