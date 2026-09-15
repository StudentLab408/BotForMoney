"""End-to-end bot scenarios against a fake Telegram API (no network) and a real SQLite database."""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    DeleteMyCommands,
    EditMessageText,
    SendDocument,
    SendMessage,
    SetMyCommands,
)
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from bot.config import Config
from bot.db import engine as db_engine
from bot.db.models import Event, Project, ProjectMember, Supplement, User
from bot.main import create_dispatcher
from bot.services.reporting import build_month_details
from bot.utils.texts import ARCHIVED_BLOCKED, CARD_ALREADY_PROCESSED_ALERT
from bot.utils.time import current_period

BOT_ID = 42
SUPER_ADMIN_ID = 900
STUDENT_ID = 100
OTHER_STUDENT_ID = 101

CONFIG = Config(
    bot_token=f"{BOT_ID}:TEST",
    super_admin_id=SUPER_ADMIN_ID,
    db_path="",
    timezone="Europe/Minsk",
    withhold_rate=Decimal("0.25"),
    project_amount=Decimal(200),
    monthly_cap=Decimal(200),
    auto_send_day=8,
    auto_send_hour=9,
)
DP = create_dispatcher(CONFIG)


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Any] = []
        self.sent: list[tuple[Any, int]] = []
        self._next_message_id = 10_000

    async def make_request(self, bot: Bot, method: Any, timeout: int | None = None) -> Any:
        self.calls.append(method)
        if isinstance(method, (SendMessage, SendDocument)):
            self._next_message_id += 1
            self.sent.append((method, self._next_message_id))
            return Message(
                message_id=self._next_message_id,
                date=dt.datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=getattr(method, "text", None),
            )
        return True

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover - not used
        raise NotImplementedError
        yield b""

    async def close(self) -> None:
        pass

    def of(self, method_type: type) -> list[Any]:
        return [c for c in self.calls if isinstance(c, method_type)]


class Harness:
    def __init__(self, bot: Bot, session: FakeSession, db_path: str) -> None:
        self.bot = bot
        self.session = session
        self.db_path = db_path
        self._update_id = 0
        self._message_id = 0

    async def _feed(self, **kwargs: Any) -> None:
        self._update_id += 1
        await DP.feed_update(self.bot, Update(update_id=self._update_id, **kwargs))

    async def send(self, user_id: int, text: str | None) -> int:
        self._message_id += 1
        await self._feed(
            message=Message(
                message_id=self._message_id,
                date=dt.datetime.now(),
                chat=Chat(id=user_id, type="private"),
                from_user=TgUser(id=user_id, is_bot=False, first_name="Test"),
                text=text,
            )
        )
        return self._message_id

    async def press(self, user_id: int, data: str, message_id: int | None = None) -> None:
        message_id = message_id or await self.screen_id(user_id)
        await self._feed(
            callback_query=CallbackQuery(
                id=f"cb{self._update_id}",
                from_user=TgUser(id=user_id, is_bot=False, first_name="Test"),
                chat_instance="test",
                data=data,
                message=Message(
                    message_id=message_id, date=dt.datetime.now(), chat=Chat(id=user_id, type="private"), text="screen"
                ),
            )
        )

    async def screen_id(self, user_id: int) -> int:
        key = StorageKey(bot_id=BOT_ID, chat_id=user_id, user_id=user_id, destiny="ui")
        return (await DP.storage.get_data(key))["screen_id"]

    def screen_text(self, user_id: int) -> str:
        texts = [
            c for c in self.session.calls if isinstance(c, (SendMessage, EditMessageText)) and c.chat_id == user_id
        ]
        return texts[-1].text

    def screen_buttons(self, user_id: int) -> dict[str, str]:
        calls = [
            c for c in self.session.calls if isinstance(c, (SendMessage, EditMessageText)) and c.chat_id == user_id
        ]
        markup = calls[-1].reply_markup
        return {b.text: b.callback_data for row in (markup.inline_keyboard if markup else []) for b in row}

    async def register(self, user_id: int, last_name: str, group: str = "10706125") -> None:
        await self.send(user_id, "/start")
        for answer in (last_name, "Имя", "Отчество", group):
            await self.send(user_id, answer)
        await self.press(user_id, "reg:confirm")

    async def one(self, model: type, **filters: Any) -> Any:
        async with db_engine.session_scope() as session:
            query = select(model).filter_by(**filters)
            return (await session.execute(query)).unique().scalar_one_or_none()

    async def all(self, model: type) -> list[Any]:
        async with db_engine.session_scope() as session:
            return list((await session.execute(select(model))).unique().scalars())

    async def restart(self) -> None:
        """Simulate a bot restart: drop all connections and reopen the same database file."""
        await db_engine.dispose_engine()
        await db_engine.init_database(self.db_path)

    async def submit_conference_with_new_event(self, user_id: int, name: str) -> None:
        await self.press(user_id, "menu:submit")
        await self.press(user_id, "sb:k:c")
        await self.press(user_id, "sb:new")
        await self.send(user_id, name)
        await self.send(user_id, "12.09.2026")
        await self.send(user_id, "RoboArm")
        await self.press(user_id, "submit:confirm")


@pytest.fixture
async def harness(tmp_path):
    db_path = str(tmp_path / "test.db")
    await db_engine.init_database(db_path)
    session = FakeSession()
    bot = Bot(CONFIG.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    yield Harness(bot, session, db_path)
    await db_engine.dispose_engine()


async def test_registration_single_window_escaping_and_restart(harness):
    calls = harness.session
    start_id = await harness.send(STUDENT_ID, "/start")
    await harness.send(STUDENT_ID, None)  # sticker/photo instead of text must not crash
    await harness.send(STUDENT_ID, "Иванов <b>&")
    await harness.restart()  # the unfinished form must survive a restart
    for answer in ("Иван", "Иванович", "10706125"):
        await harness.send(STUDENT_ID, answer)

    assert len(calls.of(SendMessage)) == 1, "every step edits the same screen"
    deleted = {d.message_id for d in calls.of(DeleteMessage)}
    assert start_id in deleted and len(deleted) == 6, "user messages are removed from the chat"
    assert "Иванов &lt;b&gt;&amp;" in harness.screen_text(STUDENT_ID)

    await harness.press(STUDENT_ID, "reg:confirm")
    user = await harness.one(User, telegram_id=STUDENT_ID)
    assert user is not None and user.last_name == "Иванов <b>&"


async def test_new_event_request_approved_from_card_and_catalog_becomes_visible(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")
    await harness.register(OTHER_STUDENT_ID, "Другов")

    await harness.submit_conference_with_new_event(STUDENT_ID, "IEEE <Robotics> 2026")
    await harness.press(STUDENT_ID, "submit:confirm")  # double tap

    [supplement] = await harness.all(Supplement)
    assert supplement.status == "pending" and supplement.project_name == "RoboArm"
    event = await harness.one(Event, id=supplement.event_id)
    assert not event.is_verified

    [(card, card_id)] = [
        (m, mid)
        for m, mid in calls.sent
        if isinstance(m, SendMessage) and m.chat_id == SUPER_ADMIN_ID and "Заявка" in m.text
    ]
    assert "IEEE &lt;Robotics&gt; 2026" in card.text

    # Hidden from other students until approved.
    await harness.press(OTHER_STUDENT_ID, "menu:submit")
    await harness.press(OTHER_STUDENT_ID, "sb:k:c")
    assert not any("IEEE" in text for text in harness.screen_buttons(OTHER_STUDENT_ID))

    await harness.press(SUPER_ADMIN_ID, f"sup:approve:{supplement.id}:12.5", card_id)
    await harness.press(SUPER_ADMIN_ID, f"sup:approve:{supplement.id}:50", card_id)

    supplement = await harness.one(Supplement, id=supplement.id)
    assert supplement.status == "approved" and supplement.amount == Decimal("12.5")
    assert supplement.period == current_period(CONFIG.timezone), "counted in the month of approval"
    assert (await harness.one(Event, id=event.id)).is_verified
    assert calls.of(AnswerCallbackQuery)[-1].text == CARD_ALREADY_PROCESSED_ALERT
    assert any(m.chat_id == STUDENT_ID and "одобрена" in m.text for m in calls.of(SendMessage))

    await harness.press(OTHER_STUDENT_ID, "sb:l:0")
    assert any("IEEE" in text for text in harness.screen_buttons(OTHER_STUDENT_ID))


async def test_queue_reject_with_reason_updates_card_and_student_can_withdraw(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")

    await harness.submit_conference_with_new_event(STUDENT_ID, "Первая")
    await harness.submit_conference_with_new_event(STUDENT_ID, "Вторая")
    first, second = sorted(await harness.all(Supplement), key=lambda s: s.id)

    await harness.send(SUPER_ADMIN_ID, "/requests")
    assert "Заявки на рассмотрении</b>: 2" in harness.screen_text(SUPER_ADMIN_ID)
    await harness.press(SUPER_ADMIN_ID, f"rq:o:{first.id}")
    await harness.press(SUPER_ADMIN_ID, f"rq:no:{first.id}")
    await harness.send(SUPER_ADMIN_ID, "Нет подтверждения")

    first = await harness.one(Supplement, id=first.id)
    assert first.status == "rejected" and first.reject_reason == "Нет подтверждения"
    card_edits = [e for e in calls.of(EditMessageText) if e.chat_id == SUPER_ADMIN_ID and "Отклонено" in e.text]
    assert card_edits, "the pushed card copy is stamped too"
    assert "Заявки на рассмотрении</b>: 1" in harness.screen_text(SUPER_ADMIN_ID)

    await harness.press(STUDENT_ID, "menu:my_submissions")
    await harness.press(STUDENT_ID, f"my:wd:{second.id}")
    await harness.press(STUDENT_ID, f"my:wdy:{second.id}")
    assert (await harness.one(Supplement, id=second.id)).status == "withdrawn"
    assert any(e.chat_id == SUPER_ADMIN_ID and "Отозвана студентом" in e.text for e in calls.of(EditMessageText))


async def test_project_membership_pays_monthly_until_removal_month(harness):
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")
    student = await harness.one(User, telegram_id=STUDENT_ID)
    admin = await harness.one(User, telegram_id=SUPER_ADMIN_ID)

    await harness.send(SUPER_ADMIN_ID, "/projects")
    await harness.press(SUPER_ADMIN_ID, "pj:new")
    await harness.send(SUPER_ADMIN_ID, "RoboArm")
    await harness.press(SUPER_ADMIN_ID, "pj:skip")
    project = await harness.one(Project, name="RoboArm")

    await harness.press(SUPER_ADMIN_ID, f"st:c:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:pj:{student.id}:0")
    await harness.press(SUPER_ADMIN_ID, f"st:pjs:{student.id}:{project.id}")
    [member] = await harness.all(ProjectMember)
    now = current_period(CONFIG.timezone)
    assert member.start_period == now and member.end_period is None

    # Simulate a membership that started two months ago and was ended this month.
    async with db_engine.session_scope() as session:
        stored = await session.get(ProjectMember, member.id)
        stored.start_period, stored.end_period, stored.removed_by = now - 2, now, admin.id
        await session.commit()
        paid = {p: bool(await build_month_details(session, CONFIG, p)) for p in (now - 3, now - 2, now - 1, now)}
    assert paid == {now - 3: False, now - 2: True, now - 1: True, now: False}


async def test_admin_awards_from_student_card_and_can_cancel(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Корецкий")
    student = await harness.one(User, telegram_id=STUDENT_ID)

    await harness.send(SUPER_ADMIN_ID, "/students")
    await harness.press(SUPER_ADMIN_ID, "st:search")
    await harness.send(SUPER_ADMIN_ID, "корец")
    assert any("Корецкий" in text for text in harness.screen_buttons(SUPER_ADMIN_ID))

    await harness.press(SUPER_ADMIN_ID, f"st:c:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:aw:{student.id}:e")
    await harness.press(SUPER_ADMIN_ID, "aw:new")
    await harness.send(SUPER_ADMIN_ID, "День науки")
    await harness.send(SUPER_ADMIN_ID, "08.09.2026")
    await harness.send(SUPER_ADMIN_ID, "Вёл мастер-класс")
    await harness.press(SUPER_ADMIN_ID, "aw:m:25")
    await harness.press(SUPER_ADMIN_ID, "aw:y")
    await harness.press(SUPER_ADMIN_ID, "aw:y")  # double tap

    [award] = await harness.all(Supplement)
    assert award.status == "approved" and award.amount == Decimal(25) and award.what_did == "Вёл мастер-класс"
    assert (await harness.one(Event, id=award.event_id)).is_verified
    assert any(m.chat_id == STUDENT_ID and "начислено 25 BYN" in m.text for m in calls.of(SendMessage))

    await harness.press(SUPER_ADMIN_ID, f"st:a:{award.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:ax:{award.id}")
    await harness.send(SUPER_ADMIN_ID, "Ошибка")
    award = await harness.one(Supplement, id=award.id)
    assert award.status == "cancelled" and award.cancel_reason == "Ошибка"
    async with db_engine.session_scope() as session:
        assert await build_month_details(session, CONFIG, current_period(CONFIG.timezone)) == []


async def test_export_sends_both_lists(harness):
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")
    await harness.submit_conference_with_new_event(STUDENT_ID, "Конф")
    [supplement] = await harness.all(Supplement)
    await harness.send(SUPER_ADMIN_ID, "/requests")
    await harness.press(SUPER_ADMIN_ID, f"rq:o:{supplement.id}")
    await harness.press(SUPER_ADMIN_ID, f"rq:ok:{supplement.id}:50")

    old_screen = await harness.screen_id(SUPER_ADMIN_ID)
    await harness.press(SUPER_ADMIN_ID, "admin:export")
    await harness.press(SUPER_ADMIN_ID, "month:export:current")
    names = sorted(d.document.filename for d in harness.session.of(SendDocument))
    assert len(names) == 2 and names[0].endswith("_internal.docx") and names[1].endswith("_official.docx")
    assert await harness.screen_id(SUPER_ADMIN_ID) != old_screen, "menu is re-sent below the files"


async def test_archive_blocks_student_and_closes_everything(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")
    student = await harness.one(User, telegram_id=STUDENT_ID)
    await harness.submit_conference_with_new_event(STUDENT_ID, "Конф")

    await harness.send(SUPER_ADMIN_ID, "/students")
    await harness.press(SUPER_ADMIN_ID, f"st:c:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:ar:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:ary:{student.id}")

    assert (await harness.one(User, id=student.id)).is_archived
    [supplement] = await harness.all(Supplement)
    assert supplement.status == "withdrawn"

    await harness.send(STUDENT_ID, "/menu")
    assert calls.of(SendMessage)[-1].chat_id == STUDENT_ID and calls.of(SendMessage)[-1].text == ARCHIVED_BLOCKED

    await harness.press(SUPER_ADMIN_ID, "st:v:arch.0")
    assert any("Студентов" in text for text in harness.screen_buttons(SUPER_ADMIN_ID))


def _commands_for(calls: FakeSession, chat_id: int) -> list[str]:
    scoped = [c for c in calls.of(SetMyCommands) if c.scope is not None and c.scope.chat_id == chat_id]
    return [command.command for command in scoped[-1].commands] if scoped else []


async def test_role_change_from_card_updates_admin_commands(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")
    student = await harness.one(User, telegram_id=STUDENT_ID)
    assert {"admin", "requests", "students", "admins"} <= set(_commands_for(calls, SUPER_ADMIN_ID))

    await harness.send(SUPER_ADMIN_ID, "/students")
    await harness.press(SUPER_ADMIN_ID, f"st:c:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:role:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:roley:{student.id}")
    assert {"admin", "requests"} <= set(_commands_for(calls, STUDENT_ID))
    assert "admins" not in _commands_for(calls, STUDENT_ID)

    await harness.press(SUPER_ADMIN_ID, f"st:role:{student.id}")
    await harness.press(SUPER_ADMIN_ID, f"st:roley:{student.id}")
    assert any(c.scope.chat_id == STUDENT_ID for c in calls.of(DeleteMyCommands))


async def test_admin_command_works_mid_form_and_is_ignored_for_students(harness):
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")

    await harness.press(SUPER_ADMIN_ID, "menu:submit")
    await harness.press(SUPER_ADMIN_ID, "sb:k:e")
    await harness.send(SUPER_ADMIN_ID, "/export")
    assert "сформировать списки" in harness.screen_text(SUPER_ADMIN_ID)

    await harness.send(STUDENT_ID, "/requests")
    assert "Заявки на рассмотрении" not in harness.screen_text(STUDENT_ID)


async def test_unknown_message_is_removed_and_unregistered_super_admin_has_no_rights(harness):
    calls = harness.session
    await harness.register(STUDENT_ID, "Студентов")
    old_screen = await harness.screen_id(STUDENT_ID)
    message_id = await harness.send(STUDENT_ID, "привет")
    deleted = {d.message_id for d in calls.of(DeleteMessage)}
    assert message_id in deleted and old_screen in deleted

    await harness.press(SUPER_ADMIN_ID, "sup:approve:1:50", old_screen)
    assert calls.of(AnswerCallbackQuery)[-1].show_alert
