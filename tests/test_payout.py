from decimal import Decimal

from bot.services.payout import AwardBasis, ProjectBasis, compute_student_month_payout, format_basis_text

PROJECT_AMOUNT = Decimal(200)
MONTHLY_CAP = Decimal(200)
WITHHOLD_RATE = Decimal("0.25")


def _compute(projects=(), awards=()):
    return compute_student_month_payout(list(projects), list(awards), PROJECT_AMOUNT, MONTHLY_CAP, WITHHOLD_RATE)


def test_project_member_gets_flat_amount():
    payout = _compute(projects=[ProjectBasis("Robo", None)])
    assert payout.basis_type == "project"
    assert payout.gross == Decimal(200)
    assert payout.withheld == Decimal(50)


def test_awards_under_cap_are_summed():
    payout = _compute(
        awards=[AwardBasis("conference", "ConfA", Decimal("12.5")), AwardBasis("event", "EvA", Decimal(25))]
    )
    assert payout.basis_type == "conf_event"
    assert payout.pre_cap_total == payout.gross == Decimal("37.5")
    assert payout.withheld == Decimal(9)  # 9.375 -> HALF_UP -> 9


def test_awards_over_cap_are_capped():
    payout = _compute(
        awards=[AwardBasis("conference", f"C{i}", Decimal(50)) for i in range(4)]
        + [AwardBasis("event", "E", Decimal(25))]
    )
    assert payout.pre_cap_total == Decimal(225)
    assert payout.gross == Decimal(200)


def test_project_overrides_awards():
    payout = _compute(projects=[ProjectBasis("Robo", None)], awards=[AwardBasis("conference", "C", Decimal(50))])
    assert payout.basis_type == "project"
    assert payout.gross == Decimal(200)


def test_nothing_means_zero():
    payout = _compute()
    assert payout.basis_type == "none"
    assert payout.gross == Decimal(0)


def test_rounding_boundary():
    payout = _compute(awards=[AwardBasis("conference", "C", Decimal("87.5"))])
    assert payout.withheld == Decimal(22)  # 21.875 -> HALF_UP -> 22


def test_basis_text():
    project = _compute(projects=[ProjectBasis("Robo", "1 место"), ProjectBasis("Drone", None)])
    assert format_basis_text(project) == "«Robo», 1 место; «Drone»"
    awards = _compute(
        awards=[AwardBasis("conference", "ConfA", Decimal(25)), AwardBasis("event", "EvB", Decimal("12.5"))]
    )
    assert format_basis_text(awards) == "Конференция «ConfA» (25 BYN); Мероприятие «EvB» (12,5 BYN)"
