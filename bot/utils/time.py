import datetime as dt
from zoneinfo import ZoneInfo

MONTH_NAMES_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

MONTH_NAMES_RU_NOMINATIVE = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
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


def month_name_genitive(month: int) -> str:
    return MONTH_NAMES_RU[month - 1]


def month_name_nominative(month: int) -> str:
    return MONTH_NAMES_RU_NOMINATIVE[month - 1]


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
