from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import Supplement, User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.services.docx_export import DocRow
from bot.services.payout import StudentMonthPayout, compute_student_month_payout, format_basis_text


@dataclass
class StudentMonthDetail:
    student: User
    payout: StudentMonthPayout
    basis_text: str


@dataclass
class MonthReport:
    year: int
    month: int
    total_amount: Decimal
    project_count: int
    project_amount: Decimal
    conference_count: int
    conference_amount: Decimal
    event_count: int
    event_amount: Decimal
    students_capped: int
    student_count: int


@dataclass
class StudentActivityReport:
    with_projects: list[User]
    with_conf_event_only: list[User]
    with_no_activity: list[User]


async def build_month_details(session: AsyncSession, config: Config, year: int, month: int) -> list[StudentMonthDetail]:
    entries = await supplements_repo.list_approved_for_month(session, year, month)
    by_student: dict[int, list[Supplement]] = defaultdict(list)
    for entry in entries:
        by_student[entry.student_id].append(entry)
    if not by_student:
        return []

    details: list[StudentMonthDetail] = []
    for student in await users_repo.get_many(session, list(by_student)):
        payout = compute_student_month_payout(
            by_student[student.id], config.project_amount, config.monthly_cap, config.withhold_rate
        )
        if payout.gross > 0:
            details.append(StudentMonthDetail(student=student, payout=payout, basis_text=format_basis_text(payout)))

    details.sort(key=lambda d: (d.student.last_name, d.student.first_name))
    return details


def _sum_amounts(details: list[StudentMonthDetail], supplement_type: str) -> tuple[int, Decimal]:
    entries = [e for d in details for e in d.payout.basis_entries if e.type == supplement_type]
    return len(entries), sum((e.amount or Decimal(0) for e in entries), Decimal(0))


async def build_month_report(session: AsyncSession, config: Config, year: int, month: int) -> MonthReport:
    details = await build_month_details(session, config, year, month)
    project_count, project_amount = _sum_amounts(details, "project")
    conference_count, conference_amount = _sum_amounts(details, "conference")
    event_count, event_amount = _sum_amounts(details, "event")

    return MonthReport(
        year=year,
        month=month,
        total_amount=sum((d.payout.gross for d in details), Decimal(0)),
        project_count=project_count,
        project_amount=project_amount,
        conference_count=conference_count,
        conference_amount=conference_amount,
        event_count=event_count,
        event_amount=event_amount,
        students_capped=sum(1 for d in details if d.payout.pre_cap_total > d.payout.gross),
        student_count=len(details),
    )


async def build_doc_rows(session: AsyncSession, config: Config, year: int, month: int) -> list[DocRow]:
    details = await build_month_details(session, config, year, month)
    return [
        DocRow(
            index=i,
            last_name=d.student.last_name,
            first_name=d.student.first_name,
            middle_name=d.student.middle_name,
            group_number=d.student.group_number,
            amount=d.payout.gross,
            withheld=d.payout.withheld,
            basis_text=d.basis_text,
        )
        for i, d in enumerate(details, start=1)
    ]


async def build_student_activity_report(session: AsyncSession) -> StudentActivityReport:
    students = await users_repo.list_students(session)
    activity = await supplements_repo.list_student_activity_types(session)

    report = StudentActivityReport(with_projects=[], with_conf_event_only=[], with_no_activity=[])
    for student in sorted(students, key=lambda u: (u.last_name, u.first_name)):
        types = activity.get(student.id, set())
        if "project" in types:
            report.with_projects.append(student)
        elif types:
            report.with_conf_event_only.append(student)
        else:
            report.with_no_activity.append(student)
    return report
