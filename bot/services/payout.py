from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Protocol


class SupplementRow(Protocol):
    type: str
    status: str
    amount: Decimal | None
    project_name: str | None
    regalia: str | None
    conference_name: str | None
    event_name: str | None


BasisType = Literal["project", "conf_event", "none"]


@dataclass
class StudentMonthPayout:
    basis_type: BasisType
    pre_cap_total: Decimal
    gross: Decimal
    withheld: Decimal
    net: Decimal
    basis_entries: list[SupplementRow]


def compute_student_month_payout(
    entries: list[SupplementRow],
    project_amount: Decimal,
    monthly_cap: Decimal,
    withhold_rate: Decimal,
) -> StudentMonthPayout:
    approved = [e for e in entries if e.status == "approved"]
    projects = [e for e in approved if e.type == "project"]
    others = [e for e in approved if e.type in ("conference", "event")]

    if projects:
        gross = project_amount
        basis_type: BasisType = "project"
        basis_entries = projects
        pre_cap_total = Decimal(0)
    elif others:
        pre_cap_total = sum((e.amount or Decimal(0) for e in others), Decimal(0))
        gross = min(pre_cap_total, monthly_cap)
        basis_type = "conf_event"
        basis_entries = others
    else:
        gross = Decimal(0)
        basis_type = "none"
        basis_entries = []
        pre_cap_total = Decimal(0)

    withheld = (gross * withhold_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    net = gross - withheld

    return StudentMonthPayout(
        basis_type=basis_type,
        pre_cap_total=pre_cap_total,
        gross=gross,
        withheld=withheld,
        net=net,
        basis_entries=basis_entries,
    )


def format_basis_text(payout: StudentMonthPayout) -> str:
    if payout.basis_type == "project":
        entry = payout.basis_entries[0]
        base = f"«{entry.project_name}»"
        if entry.regalia:
            base += f", {entry.regalia}"
        return base
    if payout.basis_type == "conf_event":
        parts = []
        for e in payout.basis_entries:
            if e.type == "conference":
                parts.append(f"Конференция «{e.conference_name}» ({e.amount} BYN)")
            else:
                parts.append(f"Мероприятие «{e.event_name}» ({e.amount} BYN)")
        return "; ".join(parts)
    return ""
