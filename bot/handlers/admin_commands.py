"""Admin "/" commands. Registered right after the common router so they work from any form state."""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.filters.roles import IsAdmin, IsSuperAdmin
from bot.handlers.admin_catalog import show_events, show_projects
from bot.handlers.admin_management import show_admin_list
from bot.handlers.admin_panel import show_admin_menu
from bot.handlers.admin_reports import open_month_picker
from bot.handlers.admin_requests import show_queue
from bot.handlers.admin_students import show_students
from bot.utils.screen import delete_message

router = Router()
router.message.filter(IsAdmin())


async def _drop_command(message: Message, bot: Bot) -> None:
    await delete_message(bot, message.chat.id, message.message_id)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, bot: Bot, session: AsyncSession, is_super_admin: bool) -> None:
    await _drop_command(message, bot)
    await show_admin_menu(state, bot, message.chat.id, session, is_super_admin, new=True)


@router.message(Command("requests"))
async def cmd_requests(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _drop_command(message, bot)
    await show_queue(state, bot, message.chat.id, session, new=True)


@router.message(Command("students"))
async def cmd_students(message: Message, state: FSMContext, bot: Bot, session: AsyncSession, config: Config) -> None:
    await _drop_command(message, bot)
    await show_students(state, bot, message.chat.id, session, config, new=True)


@router.message(Command("projects"))
async def cmd_projects(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _drop_command(message, bot)
    await show_projects(state, bot, message.chat.id, session, new=True)


@router.message(Command("events"))
async def cmd_events(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _drop_command(message, bot)
    await show_events(state, bot, message.chat.id, session, "conference", new=True)


@router.message(Command("report", "export"))
async def cmd_month_picker(message: Message, state: FSMContext, bot: Bot, command: CommandObject) -> None:
    await _drop_command(message, bot)
    await open_month_picker(state, bot, message.chat.id, command.command, new=True)


@router.message(Command("admins"), IsSuperAdmin())
async def cmd_admins(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await _drop_command(message, bot)
    await show_admin_list(state, bot, message.chat.id, session, new=True)
