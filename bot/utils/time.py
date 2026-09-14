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


def current_period(timezone: str) -> tuple[int, int]:
    moment = now(timezone)
    return moment.year, moment.month


def previous_period(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def month_name(month: int) -> str:
    return MONTH_NAMES[month - 1]


def format_datetime(moment: dt.datetime, timezone: str) -> str:
    """Format a timestamp in the configured zone; naive values are treated as UTC (how SQLite stores them)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment.astimezone(ZoneInfo(timezone)).strftime("%d.%m.%Y %H:%M")


def parse_month_string(raw: str) -> tuple[int, int] | None:
    """Parse 'MM.YYYY' into (year, month), or None if invalid."""
    parts = raw.strip().split(".")
    if len(parts) != 2:
        return None
    month_str, year_str = parts
    if not (month_str.isdigit() and year_str.isdigit()):
        return None
    month, year = int(month_str), int(year_str)
    if not (1 <= month <= 12) or year < 2000:
        return None
    return year, month
