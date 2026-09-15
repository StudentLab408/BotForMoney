"""Human-readable explanations of how money is counted, shared by student and admin screens and notifications."""

from decimal import Decimal

from bot.config import ALLOWED_CONF_EVENT_AMOUNTS, Config
from bot.db.models import ProjectMember
from bot.services.payout import StudentMonthPayout
from bot.utils.format import h, money
from bot.utils.texts import (
    AWARD_NOTE_CAPPED,
    AWARD_NOTE_PROJECT,
    KIND_TEXT,
    NOTE_CAPPED,
    NOTE_PROJECT_OVERRIDES,
    PAYOUT_NOTHING,
    PAYOUT_TOTAL,
    RULES_TEXT,
)
from bot.utils.time import format_period, period_title


def membership_span(member: ProjectMember, current_period: int) -> str:
    """'с 06.2026 · 4 мес., включая текущий', '03.2026–05.2026 · 3 мес.' or 'не оплачивался'."""
    start = member.start_period
    if member.end_period is None:
        months = max(current_period - start + 1, 0)
        return f"с {format_period(start)} · {months} мес., включая текущий"
    if member.end_period <= start:
        return f"{format_period(start)} · не оплачивался (убран в том же месяце)"
    return f"{format_period(start)}–{format_period(member.end_period - 1)} · {member.end_period - start} мес."


def paid_until_text(member: ProjectMember) -> str:
    if member.end_period is None or member.end_period <= member.start_period:
        return "не начислялась"
    return f"начислена за {format_period(member.start_period)}–{format_period(member.end_period - 1)}"


def month_breakdown(payout: StudentMonthPayout, config: Config) -> list[str]:
    """Every line that makes up one month's amount, including what was approved but not added."""
    if payout.basis_type == "none":
        return [PAYOUT_NOTHING]
    if payout.basis_type == "project":
        project_amount = money(config.project_amount)
        first, *others = payout.projects
        lines = [f"📁 Проект «{h(first.name)}» — {project_amount} BYN"]
        lines += [f"📁 Проект «{h(p.name)}» — входит в те же {project_amount} BYN" for p in others]
        if payout.awards:
            total = sum((a.amount for a in payout.awards), Decimal(0))
            note = NOTE_PROJECT_OVERRIDES.format(count=len(payout.awards), amount=money(total), project=project_amount)
            lines.append(note)
    else:
        lines = [f"{KIND_TEXT[a.kind]['icon']} «{h(a.event_name)}» — {money(a.amount)} BYN" for a in payout.awards]
        if payout.pre_cap_total > payout.gross:
            lines.append(NOTE_CAPPED.format(total=money(payout.pre_cap_total), cap=money(config.monthly_cap)))
    lines.append(PAYOUT_TOTAL.format(amount=money(payout.gross)))
    return lines


def month_block(title: str, payout: StudentMonthPayout, config: Config) -> str:
    return "\n".join([title, *month_breakdown(payout, config)])


def award_note(payout: StudentMonthPayout, config: Config) -> str:
    """Appended to an approval notification when the approved amount is not simply added."""
    if payout.basis_type == "project":
        return AWARD_NOTE_PROJECT.format(project=money(config.project_amount))
    if payout.pre_cap_total > payout.gross:
        return AWARD_NOTE_CAPPED.format(total=money(payout.pre_cap_total), cap=money(config.monthly_cap))
    return ""


def rules_text(config: Config) -> str:
    return RULES_TEXT.format(
        project=money(config.project_amount),
        cap=money(config.monthly_cap),
        amounts=" / ".join(money(a) for a in ALLOWED_CONF_EVENT_AMOUNTS),
        day=config.auto_send_day,
    )


def month_title(period: int, current_period: int) -> str:
    label = period_title(period).capitalize()
    if period == current_period:
        return f"📅 <b>{label}</b> — текущий месяц, ещё может измениться"
    if period == current_period - 1:
        return f"📅 <b>{label}</b> — прошлый месяц"
    return f"📅 <b>{label}</b>"
