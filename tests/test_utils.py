import datetime as dt
from decimal import Decimal

from bot.keyboards.builders import page_slice
from bot.utils.format import h, money, split_message
from bot.utils.input import validate_text
from bot.utils.time import (
    format_datetime,
    format_period,
    from_period,
    parse_date,
    parse_month_string,
    period_title,
    to_period,
)


def test_money_strips_trailing_zeros_and_uses_comma():
    assert money(Decimal("200.00")) == "200"
    assert money(Decimal("37.50")) == "37,5"
    assert money(Decimal("0.00")) == "0"


def test_h_escapes_html():
    assert h("A <b> & C") == "A &lt;b&gt; &amp; C"


def test_split_message_respects_limit_and_keeps_content():
    text = "\n".join(f"line {i}" for i in range(1000))
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text
    assert [len(c) for c in split_message("x" * 250, limit=100)] == [100, 100, 50]


def test_validate_text():
    assert validate_text("  Иванов ", 100) == ("Иванов", None)
    assert validate_text(None, 100)[0] is None
    assert validate_text("/menu", 100)[0] is None
    assert validate_text("x" * 101, 100)[0] is None


def test_periods():
    september = to_period(2026, 9)
    assert from_period(september) == (2026, 9)
    assert from_period(to_period(2026, 1) - 1) == (2025, 12)
    assert format_period(september) == "09.2026"
    assert period_title(september) == "сентябрь 2026"
    assert parse_month_string("09.2026") == september
    assert parse_month_string("13.2026") is None


def test_parse_date():
    assert parse_date("12.09.2026") == dt.date(2026, 9, 12)
    assert parse_date("31.02.2026") is None
    assert parse_date("вчера") is None


def test_format_datetime_treats_naive_as_utc():
    assert format_datetime(dt.datetime(2026, 9, 15, 9, 0), "Europe/Minsk") == "15.09.2026 12:00"


def test_page_slice_clamps_page():
    items = list(range(20))
    assert page_slice(items, 0, 8) == (list(range(8)), 0, 3)
    assert page_slice(items, 9, 8) == ([16, 17, 18, 19], 2, 3)
    assert page_slice([], 3, 8) == ([], 0, 1)
