from dataclasses import dataclass
from decimal import Decimal

from bot.services.payout import compute_student_month_payout, format_basis_text

PROJECT_AMOUNT = Decimal(200)
MONTHLY_CAP = Decimal(200)
WITHHOLD_RATE = Decimal("0.25")


@dataclass
class Row:
    type: str
    status: str = "approved"
    amount: Decimal | None = None
    project_name: str | None = None
    regalia: str | None = None
    conference_name: str | None = None
    event_name: str | None = None


def _compute(entries):
    return compute_student_month_payout(entries, PROJECT_AMOUNT, MONTHLY_CAP, WITHHOLD_RATE)


def test_project_only():
    payout = _compute([Row(type="project", amount=Decimal(200), project_name="Robo")])
    assert payout.basis_type == "project"
    assert payout.gross == Decimal(200)
    assert payout.withheld == Decimal(50)
    assert payout.net == Decimal(150)


def test_conf_event_under_cap():
    entries = [
        Row(type="conference", amount=Decimal("12.5"), conference_name="ConfA"),
        Row(type="event", amount=Decimal("25"), event_name="EventA"),
    ]
    payout = _compute(entries)
    assert payout.basis_type == "conf_event"
    assert payout.pre_cap_total == Decimal("37.5")
    assert payout.gross == Decimal("37.5")
    assert payout.withheld == Decimal(9)  # round(9.375) -> HALF_UP -> 9
    assert payout.net == Decimal("28.5")


def test_conf_event_exceeds_cap():
    entries = [
        Row(type="conference", amount=Decimal(50)),
        Row(type="conference", amount=Decimal(50)),
        Row(type="event", amount=Decimal(50)),
        Row(type="event", amount=Decimal(50)),
        Row(type="event", amount=Decimal(25)),
    ]
    payout = _compute(entries)
    assert payout.pre_cap_total == Decimal(225)
    assert payout.gross == Decimal(200)
    assert len(payout.basis_entries) == 5


def test_project_overrides_conf_event():
    entries = [
        Row(type="project", amount=Decimal(200), project_name="Robo"),
        Row(type="conference", amount=Decimal(50)),
    ]
    payout = _compute(entries)
    assert payout.basis_type == "project"
    assert payout.gross == Decimal(200)


def test_no_approved_entries():
    entries = [Row(type="conference", amount=None, status="pending")]
    payout = _compute(entries)
    assert payout.basis_type == "none"
    assert payout.gross == Decimal(0)
    assert payout.net == Decimal(0)


def test_rounding_boundary():
    entries = [Row(type="conference", amount=Decimal("87.5"))]
    payout = _compute(entries)
    assert payout.gross == Decimal("87.5")
    assert payout.withheld == Decimal(22)  # 21.875 -> HALF_UP -> 22
    assert payout.net == Decimal("65.5")


def test_format_basis_text_project():
    payout = _compute([Row(type="project", amount=Decimal(200), project_name="Robo", regalia="1 место")])
    assert format_basis_text(payout) == "«Robo», 1 место"


def test_format_basis_text_conf_event():
    entries = [
        Row(type="conference", amount=Decimal(25), conference_name="ConfA"),
        Row(type="event", amount=Decimal(50), event_name="EventB"),
    ]
    payout = _compute(entries)
    text = format_basis_text(payout)
    assert "Конференция «ConfA» (25 BYN)" in text
    assert "Мероприятие «EventB» (50 BYN)" in text
