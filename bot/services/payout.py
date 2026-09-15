"""Monthly payout rules, free of Telegram and database code."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from bot.utils.format import money

BasisType = Literal["project", "conf_event", "none"]
KIND_LABELS = {"conference": "Конференция", "event": "Мероприятие"}


@dataclass(frozen=True)
class ProjectBasis:
    name: str
    regalia: str | None


@dataclass(frozen=True)
class AwardBasis:
    kind: str
    event_name: str
    amount: Decimal


@dataclass
class StudentMonthPayout:
    basis_type: BasisType
    pre_cap_total: Decimal
    gross: Decimal
    withheld: Decimal
    projects: list[ProjectBasis]
    awards: list[AwardBasis]


def compute_student_month_payout(
    projects: list[ProjectBasis],
    awards: list[AwardBasis],
    project_amount: Decimal,
    monthly_cap: Decimal,
    withhold_rate: Decimal,
) -> StudentMonthPayout:
    """Project membership pays a flat amount and overrides awards; otherwise awards are summed up to the cap."""
    if projects:
        basis_type: BasisType = "project"
        pre_cap_total = Decimal(0)
        gross = project_amount
    elif awards:
        basis_type = "conf_event"
        pre_cap_total = sum((a.amount for a in awards), Decimal(0))
        gross = min(pre_cap_total, monthly_cap)
    else:
        basis_type = "none"
        pre_cap_total = gross = Decimal(0)

    withheld = (gross * withhold_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return StudentMonthPayout(basis_type, pre_cap_total, gross, withheld, projects, awards)


def format_basis_text(payout: StudentMonthPayout) -> str:
    if payout.basis_type == "project":
        return "; ".join(f"«{p.name}»" + (f", {p.regalia}" if p.regalia else "") for p in payout.projects)
    if payout.basis_type == "conf_event":
        return "; ".join(
            f"{KIND_LABELS.get(a.kind, a.kind)} «{a.event_name}» ({money(a.amount)} BYN)" for a in payout.awards
        )
    return ""
