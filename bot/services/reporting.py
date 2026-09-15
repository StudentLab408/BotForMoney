from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.db.models import User
from bot.db.repo import projects as projects_repo
from bot.db.repo import supplements as supplements_repo
from bot.db.repo import users as users_repo
from bot.services.docx_export import DocRow
from bot.services.payout import (
    AwardBasis,
    ProjectBasis,
    StudentMonthPayout,
    compute_student_month_payout,
    format_basis_text,
)


@dataclass
class StudentMonthDetail:
    student: User
    payout: StudentMonthPayout
    basis_text: str


@dataclass
class MonthReport:
    period: int
    total_amount: Decimal
    project_students: int
    project_amount: Decimal
    conference_count: int
    conference_amount: Decimal
    event_count: int
    event_amount: Decimal
    students_capped: int
    student_count: int


@dataclass
class StudentStats:
    current_projects: list[str] = field(default_factory=list)
    ever_in_project: bool = False
    approved: int = 0
    pending: int = 0

    @property
    def is_idle(self) -> bool:
        return not self.ever_in_project and self.approved == 0 and self.pending == 0


async def build_month_details(session: AsyncSession, config: Config, period: int) -> list[StudentMonthDetail]:
    projects: dict[int, list[ProjectBasis]] = defaultdict(list)
    awards: dict[int, list[AwardBasis]] = defaultdict(list)
    students: dict[int, User] = {}

    for member in await projects_repo.list_paid_memberships(session, period):
        projects[member.user_id].append(ProjectBasis(member.project.name, member.project.regalia))
        students[member.user_id] = member.user
    for supplement in await supplements_repo.list_approved_for_period(session, period):
        awards[supplement.student_id].append(
            AwardBasis(supplement.event.kind, supplement.event.name, supplement.amount or Decimal(0))
        )
        students[supplement.student_id] = supplement.student

    details = []
    for user_id, student in students.items():
        payout = compute_student_month_payout(
            projects[user_id], awards[user_id], config.project_amount, config.monthly_cap, config.withhold_rate
        )
        details.append(StudentMonthDetail(student, payout, format_basis_text(payout)))
    details.sort(key=lambda d: (d.student.last_name, d.student.first_name, d.student.middle_name))
    return details


async def build_month_report(session: AsyncSession, config: Config, period: int) -> MonthReport:
    details = await build_month_details(session, config, period)
    project_details = [d for d in details if d.payout.basis_type == "project"]
    counted_awards = [a for d in details if d.payout.basis_type == "conf_event" for a in d.payout.awards]
    conferences = [a for a in counted_awards if a.kind == "conference"]
    events = [a for a in counted_awards if a.kind == "event"]

    return MonthReport(
        period=period,
        total_amount=sum((d.payout.gross for d in details), Decimal(0)),
        project_students=len(project_details),
        project_amount=sum((d.payout.gross for d in project_details), Decimal(0)),
        conference_count=len(conferences),
        conference_amount=sum((a.amount for a in conferences), Decimal(0)),
        event_count=len(events),
        event_amount=sum((a.amount for a in events), Decimal(0)),
        students_capped=sum(1 for d in details if d.payout.pre_cap_total > d.payout.gross),
        student_count=len(details),
    )


async def build_doc_rows(session: AsyncSession, config: Config, period: int) -> list[DocRow]:
    details = await build_month_details(session, config, period)
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


async def build_student_stats(session: AsyncSession) -> dict[int, StudentStats]:
    """Activity markers for every user, used by the admin students list."""
    stats: dict[int, StudentStats] = defaultdict(StudentStats)
    for member in await projects_repo.list_current_memberships(session):
        stats[member.user_id].current_projects.append(member.project.name)
    for user_id in await projects_repo.list_member_user_ids_ever(session):
        stats[user_id].ever_in_project = True
    for student_id, counts in (await supplements_repo.status_counts_by_student(session)).items():
        stats[student_id].approved = counts.get("approved", 0)
        stats[student_id].pending = counts.get("pending", 0)
    return stats


async def student_month_payout(
    session: AsyncSession, config: Config, user_id: int, period: int
) -> StudentMonthPayout | None:
    for detail in await build_month_details(session, config, period):
        if detail.student.id == user_id:
            return detail.payout
    return None


async def list_users_for_filter(
    session: AsyncSession, stats: dict[int, StudentStats], filter_code: str, group: str | None = None
) -> list[User]:
    if filter_code == "arch":
        return await users_repo.list_all(session, archived=True)
    users = await users_repo.list_all(session)
    if filter_code == "proj":
        return [u for u in users if stats[u.id].current_projects]
    if filter_code == "conf":
        return [u for u in users if stats[u.id].approved]
    if filter_code == "idle":
        return [u for u in users if stats[u.id].is_idle]
    if filter_code == "grp" and group is not None:
        return [u for u in users if u.group_number == group]
    return users
