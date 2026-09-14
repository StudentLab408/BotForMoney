from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.services.payout import StudentMonthPayout, compute_student_month_payout, format_basis_text


@dataclass
class DocRow:
    index: int
    last_name: str
    first_name: str
    middle_name: str
    group_number: str
    net_amount: Decimal
    basis_text: str


@dataclass
class StudentMonthDetail:
    student: User
    payout: StudentMonthPayout
    basis_text: str


@dataclass
class MonthReport:
    year: int
    month: int
    total_gross: Decimal
    total_withheld: Decimal
    total_net: Decimal
    project_count: int
    project_gross: Decimal
    conference_count: int
    conference_gross: Decimal
    event_count: int
    event_gross: Decimal
    students_capped: int
    student_count: int
    details: list[StudentMonthDetail]


@dataclass
class StudentActivityReport:
    with_projects: list[User]
    with_conf_event_only: list[User]
    with_no_activity: list[User]


async def _student_month_detail(
    session: AsyncSession, config: Config, student: User, year: int, month: int
) -> StudentMonthDetail | None:
    entries = await supplements_repo.list_for_student_month(session, student.id, year, month)
    payout = compute_student_month_payout(
        entries, config.project_amount, config.monthly_cap, config.withhold_rate
    )
    if payout.gross <= 0:
        return None
    return StudentMonthDetail(student=student, payout=payout, basis_text=format_basis_text(payout))


async def build_month_details(
    session: AsyncSession, config: Config, year: int, month: int
) -> list[StudentMonthDetail]:
    student_ids = await supplements_repo.list_students_with_activity(session, year, month)
    details: list[StudentMonthDetail] = []
    for student_id in student_ids:
        student = await session.get(User, student_id)
        if student is None:
            continue
        detail = await _student_month_detail(session, config, student, year, month)
        if detail is not None:
            details.append(detail)
    return details


async def build_month_report(session: AsyncSession, config: Config, year: int, month: int) -> MonthReport:
    details = await build_month_details(session, config, year, month)

    total_gross = sum((d.payout.gross for d in details), Decimal(0))
    total_withheld = sum((d.payout.withheld for d in details), Decimal(0))
    total_net = sum((d.payout.net for d in details), Decimal(0))

    project_details = [d for d in details if d.payout.basis_type == "project"]
    conf_event_details = [d for d in details if d.payout.basis_type == "conf_event"]

    conference_count = sum(
        1 for d in conf_event_details for e in d.payout.basis_entries if e.type == "conference"
    )
    event_count = sum(
        1 for d in conf_event_details for e in d.payout.basis_entries if e.type == "event"
    )
    conference_gross = sum(
        (e.amount or Decimal(0) for d in conf_event_details for e in d.payout.basis_entries if e.type == "conference"),
        Decimal(0),
    )
    event_gross = sum(
        (e.amount or Decimal(0) for d in conf_event_details for e in d.payout.basis_entries if e.type == "event"),
        Decimal(0),
    )
    students_capped = sum(1 for d in conf_event_details if d.payout.pre_cap_total > d.payout.gross)

    return MonthReport(
        year=year,
        month=month,
        total_gross=total_gross,
        total_withheld=total_withheld,
        total_net=total_net,
        project_count=len(project_details),
        project_gross=sum((d.payout.gross for d in project_details), Decimal(0)),
        conference_count=conference_count,
        conference_gross=conference_gross,
        event_count=event_count,
        event_gross=event_gross,
        students_capped=students_capped,
        student_count=len(details),
        details=details,
    )


async def build_doc_rows(session: AsyncSession, config: Config, year: int, month: int) -> list[DocRow]:
    details = await build_month_details(session, config, year, month)
    details.sort(key=lambda d: (d.student.last_name, d.student.first_name))
    return [
        DocRow(
            index=i,
            last_name=d.student.last_name,
            first_name=d.student.first_name,
            middle_name=d.student.middle_name,
            group_number=d.student.group_number,
            net_amount=d.payout.net,
            basis_text=d.basis_text,
        )
        for i, d in enumerate(details, start=1)
    ]


async def build_student_activity_report(session: AsyncSession) -> StudentActivityReport:
    students = await users_repo.list_students(session)
    activity = await supplements_repo.list_student_activity_types(session)

    with_projects: list[User] = []
    with_conf_event_only: list[User] = []
    with_no_activity: list[User] = []

    for student in sorted(students, key=lambda u: (u.last_name, u.first_name)):
        types = activity.get(student.id, set())
        if "project" in types:
            with_projects.append(student)
        elif types:
            with_conf_event_only.append(student)
        else:
            with_no_activity.append(student)

    return StudentActivityReport(
        with_projects=with_projects,
        with_conf_event_only=with_conf_event_only,
        with_no_activity=with_no_activity,
    )
