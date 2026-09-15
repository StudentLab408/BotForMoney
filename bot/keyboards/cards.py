from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.admin import amount_row
from bot.keyboards.builders import button, markup


def request_card_keyboard(supplement_id: int) -> InlineKeyboardMarkup:
    """Buttons on the request card pushed to every admin."""
    return markup(
        amount_row(lambda amount: f"sup:approve:{supplement_id}:{amount}"),
        [button("❌ Отклонить", f"sup:reject:{supplement_id}")],
    )
