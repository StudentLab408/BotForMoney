import os
from dataclasses import dataclass, field
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

ALLOWED_CONF_EVENT_AMOUNTS: list[Decimal] = [Decimal("12.5"), Decimal("25"), Decimal("50")]


@dataclass(frozen=True)
class Config:
    bot_token: str
    super_admin_id: int
    db_path: str
    timezone: str
    withhold_rate: Decimal
    project_amount: Decimal
    monthly_cap: Decimal
    auto_send_day: int
    auto_send_hour: int


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    super_admin_raw = os.getenv("SUPER_ADMIN_ID", "")
    if not super_admin_raw:
        raise RuntimeError("SUPER_ADMIN_ID is not set in .env")

    return Config(
        bot_token=bot_token,
        super_admin_id=int(super_admin_raw),
        db_path=os.getenv("DB_PATH", "./data/nadbavki.db"),
        timezone=os.getenv("TIMEZONE", "Europe/Minsk"),
        withhold_rate=Decimal(os.getenv("WITHHOLD_RATE", "0.25")),
        project_amount=Decimal(os.getenv("PROJECT_AMOUNT", "200")),
        monthly_cap=Decimal(os.getenv("MONTHLY_CAP", "200")),
        auto_send_day=int(os.getenv("AUTO_SEND_DAY", "8")),
        auto_send_hour=int(os.getenv("AUTO_SEND_HOUR", "9")),
    )
