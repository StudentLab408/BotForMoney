import html
from decimal import Decimal

TELEGRAM_SAFE_MESSAGE_LEN = 4000


def h(value: object) -> str:
    """Escape user-provided text before inserting it into an HTML-formatted message."""
    return html.escape(str(value), quote=False)


def money(value: Decimal) -> str:
    """200.00 -> '200', 37.50 -> '37,5'."""
    return f"{value.normalize():f}".replace(".", ",")


def split_message(text: str, limit: int = TELEGRAM_SAFE_MESSAGE_LEN) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    chunks.append(current)
    return chunks
