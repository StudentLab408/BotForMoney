import datetime as dt
from decimal import Decimal

from bot.utils.format import h, money, split_message
from bot.utils.input import validate_text
from bot.utils.time import format_datetime, month_name, parse_month_string, previous_period


def test_money_strips_trailing_zeros_and_uses_comma():
    assert money(Decimal("200.00")) == "200"
    assert money(Decimal("37.50")) == "37,5"
    assert money(Decimal("12.5")) == "12,5"
    assert money(Decimal("0.00")) == "0"


def test_h_escapes_html():
    assert h("A <b> & C") == "A &lt;b&gt; &amp; C"


def test_split_message_respects_limit_and_keeps_content():
    text = "\n".join(f"line {i}" for i in range(1000))
    chunks = split_message(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text


def test_split_message_handles_single_long_line():
    chunks = split_message("x" * 250, limit=100)
    assert [len(c) for c in chunks] == [100, 100, 50]


def test_validate_text():
    assert validate_text("  Иванов ", 100) == ("Иванов", None)
    assert validate_text(None, 100)[0] is None
    assert validate_text("/menu", 100)[0] is None
    assert validate_text("x" * 101, 100)[0] is None


def test_month_helpers():
    assert parse_month_string("09.2026") == (2026, 9)
    assert parse_month_string("13.2026") is None
    assert parse_month_string("sept") is None
    assert previous_period(2026, 1) == (2025, 12)
    assert month_name(9) == "сентябрь"


def test_format_datetime_treats_naive_as_utc():
    assert format_datetime(dt.datetime(2026, 9, 15, 9, 0), "Europe/Minsk") == "15.09.2026 12:00"
