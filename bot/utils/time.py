"""Time helpers. A "period" is a calendar month stored as one int: year * 12 + (month - 1)."""

import datetime as dt
from zoneinfo import ZoneInfo

MONTH_NAMES = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]


def now(timezone: str) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(timezone))


def to_period(year: int, month: int) -> int:
    return year * 12 + month - 1


def from_period(period: int) -> tuple[int, int]:
    year, month_index = divmod(period, 12)
    return year, month_index + 1


def current_period(timezone: str) -> int:
    moment = now(timezone)
    return to_period(moment.year, moment.month)


def period_title(period: int) -> str:
    """'сентябрь 2026'."""
    year, month = from_period(period)
    return f"{MONTH_NAMES[month - 1]} {year}"


def format_period(period: int) -> str:
    """'09.2026'."""
    year, month = from_period(period)
    return f"{month:02d}.{year}"


def format_datetime(moment: dt.datetime, timezone: str) -> str:
    """Format a timestamp in the configured zone; naive values are treated as UTC (how SQLite stores them)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")


def format_date(value: dt.date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_month_string(raw: str) -> int | None:
    """Parse 'MM.YYYY' into a period, or None if invalid."""
    parts = raw.strip().split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    month, year = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12) or year < 2000:
        return None
    return to_period(year, month)


def parse_date(raw: str) -> dt.date | None:
    """Parse 'ДД.ММ.ГГГГ', or None if invalid."""
    try:
        value = dt.datetime.strptime(raw.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None
    return value if value.year >= 2000 else None
