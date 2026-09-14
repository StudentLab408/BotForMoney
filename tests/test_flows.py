"""End-to-end bot scenarios against a fake Telegram API (no network)."""

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import AnswerCallbackQuery, DeleteMessage, EditMessageText, SendDocument, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from bot.config import Config
from bot.db import engine as db_engine
from bot.db.models import Supplement, User
from bot.main import create_dispatcher
from bot.utils.texts import CARD_ALREADY_PROCESSED_ALERT

BOT_ID = 42
SUPER_ADMIN_ID = 900
STUDENT_ID = 100

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
    def __init__(self, bot: Bot, session: FakeSession) -> None:
        self.bot = bot
        self.session = session
        self._update_id = 0
        self._message_id = 0

    def _user(self, user_id: int) -> TgUser:
        return TgUser(id=user_id, is_bot=False, first_name="Test")

    async def _feed(self, **kwargs: Any) -> None:
        self._update_id += 1
        await DP.feed_update(self.bot, Update(update_id=self._update_id, **kwargs))

    async def send(self, user_id: int, text: str | None) -> int:
        self._message_id += 1
        message = Message(
            message_id=self._message_id,
            date=dt.datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=self._user(user_id),
            text=text,
        )
        await self._feed(message=message)
        return self._message_id

    async def press(self, user_id: int, data: str, message_id: int) -> None:
        callback = CallbackQuery(
            id=f"cb{self._update_id}",
            from_user=self._user(user_id),
            chat_instance="test",
            data=data,
            message=Message(
                message_id=message_id, date=dt.datetime.now(), chat=Chat(id=user_id, type="private"), text="screen"
            ),
        )
        await self._feed(callback_query=callback)

    async def screen_id(self, user_id: int) -> int:
        key = StorageKey(bot_id=BOT_ID, chat_id=user_id, user_id=user_id, destiny="ui")
        return (await DP.storage.get_data(key))["screen_id"]

    async def register(self, user_id: int, last_name: str) -> None:
        await self.send(user_id, "/start")
        for answer in (last_name, "Имя", "Отчество", "10706125"):
            await self.send(user_id, answer)
        await self.press(user_id, "reg:confirm", await self.screen_id(user_id))

    async def user(self, telegram_id: int) -> User | None:
        async with db_engine.session_scope() as session:
            return (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()

    async def supplements(self) -> list[Supplement]:
        async with db_engine.session_scope() as session:
            return list((await session.execute(select(Supplement))).scalars())


@pytest.fixture
async def harness(tmp_path):
    DP.storage.storage.clear()
    await db_engine.init_models(str(tmp_path / "test.db"))
    session = FakeSession()
    bot = Bot(CONFIG.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    yield Harness(bot, session)
    await db_engine.dispose_engine()


async def test_registration_uses_single_window_and_escapes_input(harness):
    calls = harness.session
    start_id = await harness.send(STUDENT_ID, "/start")
    await harness.send(STUDENT_ID, None)  # sticker/photo instead of text must not crash
    for answer in ("Иванов <b>&", "Иван", "Иванович", "10706125"):
        await harness.send(STUDENT_ID, answer)

    assert len(calls.of(SendMessage)) == 1, "every step must edit the same screen"
    deleted = {d.message_id for d in calls.of(DeleteMessage)}
    assert start_id in deleted and len(deleted) == 6, "user messages are removed from the chat"
    assert "Иванов &lt;b&gt;&amp;" in calls.of(EditMessageText)[-1].text

    await harness.press(STUDENT_ID, "reg:confirm", await harness.screen_id(STUDENT_ID))
    user = await harness.user(STUDENT_ID)
    assert user is not None and user.last_name == "Иванов <b>&"


async def test_submission_approval_double_taps_and_export(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Студентов")

    screen = await harness.screen_id(STUDENT_ID)
    await harness.press(STUDENT_ID, "menu:submit", screen)
    await harness.press(STUDENT_ID, "submit_type:conference", screen)
    await harness.send(STUDENT_ID, "IEEE <Robotics>")
    await harness.send(STUDENT_ID, "RoboArm")
    await harness.press(STUDENT_ID, "submit:confirm", screen)
    await harness.press(STUDENT_ID, "submit:confirm", screen)  # double tap

    [supplement] = await harness.supplements()
    [(card, card_id)] = [
        (m, mid)
        for m, mid in calls.sent
        if isinstance(m, SendMessage) and m.chat_id == SUPER_ADMIN_ID and "Новая заявка" in m.text
    ]
    assert "IEEE &lt;Robotics&gt;" in card.text

    await harness.press(SUPER_ADMIN_ID, f"sup:approve:{supplement.id}:12.5", card_id)
    await harness.press(SUPER_ADMIN_ID, f"sup:approve:{supplement.id}:50", card_id)

    [supplement] = await harness.supplements()
    assert supplement.status == "approved" and supplement.amount == Decimal("12.5")
    assert calls.of(AnswerCallbackQuery)[-1].text == CARD_ALREADY_PROCESSED_ALERT
    assert any(m.chat_id == STUDENT_ID and "одобрена" in m.text and "12,5" in m.text for m in calls.of(SendMessage))

    admin_screen = await harness.screen_id(SUPER_ADMIN_ID)
    await harness.press(SUPER_ADMIN_ID, "menu:admin", admin_screen)
    await harness.press(SUPER_ADMIN_ID, "admin:export", admin_screen)
    await harness.press(SUPER_ADMIN_ID, "month:export:current", admin_screen)

    filenames = sorted(d.document.filename for d in calls.of(SendDocument))
    assert len(filenames) == 2 and filenames[0].endswith("_internal.docx") and filenames[1].endswith("_official.docx")
    assert await harness.screen_id(SUPER_ADMIN_ID) != admin_screen, "menu is re-sent below the files"
    assert admin_screen in {d.message_id for d in calls.of(DeleteMessage)}


async def test_project_entry_search_is_case_insensitive_and_report_has_no_lab_share(harness):
    calls = harness.session
    await harness.register(SUPER_ADMIN_ID, "Админов")
    await harness.register(STUDENT_ID, "Корецкий")

    screen = await harness.screen_id(SUPER_ADMIN_ID)
    await harness.press(SUPER_ADMIN_ID, "admin:project_entry", screen)
    await harness.send(SUPER_ADMIN_ID, "корец")
    button = calls.of(EditMessageText)[-1].reply_markup.inline_keyboard[0][0]
    assert "Корецкий" in button.text

    await harness.press(SUPER_ADMIN_ID, button.callback_data, screen)
    await harness.send(SUPER_ADMIN_ID, "Robo")
    await harness.send(SUPER_ADMIN_ID, "1 место")
    await harness.press(SUPER_ADMIN_ID, "admin:project_confirm", screen)
    await harness.press(SUPER_ADMIN_ID, "admin:project_confirm", screen)  # double tap
    assert len(await harness.supplements()) == 1

    await harness.press(SUPER_ADMIN_ID, "admin:report", screen)
    await harness.press(SUPER_ADMIN_ID, "month:report:current", screen)
    report = calls.of(EditMessageText)[-1].text
    assert "Итого начислено: 200 BYN" in report
    assert "25%" not in report and "Удерж" not in report


async def test_unknown_message_is_removed_and_menu_shown_at_bottom(harness):
    calls = harness.session
    await harness.register(STUDENT_ID, "Студентов")
    old_screen = await harness.screen_id(STUDENT_ID)

    message_id = await harness.send(STUDENT_ID, "привет")

    deleted = {d.message_id for d in calls.of(DeleteMessage)}
    assert message_id in deleted and old_screen in deleted
    assert await harness.screen_id(STUDENT_ID) != old_screen


async def test_unregistered_super_admin_has_no_admin_rights(harness):
    await harness.register(STUDENT_ID, "Студентов")
    screen = await harness.screen_id(STUDENT_ID)
    await harness.press(SUPER_ADMIN_ID, "sup:approve:1:50", screen)
    assert harness.session.of(AnswerCallbackQuery)[-1].show_alert  # handled by fallback, no crash
