"""Admin "/" commands. Registered right after the common router so they work from any form state."""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.roles import IsAdmin, IsSuperAdmin
from bot.handlers.admin_management import show_admin_list
from bot.handlers.admin_panel import show_admin_menu
from bot.handlers.admin_project_entry import start_project_entry
from bot.handlers.admin_reports import open_month_picker, show_activity
from bot.utils.screen import delete_message

router = Router()
router.message.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, bot: Bot, is_super_admin: bool) -> None:
    await state.clear()
    await delete_message(bot, message.chat.id, message.message_id)
    await show_admin_menu(state, bot, message.chat.id, is_super_admin, new=True)


@router.message(Command("project"))
async def cmd_project(message: Message, state: FSMContext, bot: Bot) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    await start_project_entry(state, bot, message.chat.id, new=True)


@router.message(Command("report", "export"))
async def cmd_month_picker(message: Message, state: FSMContext, bot: Bot, command: CommandObject) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    await open_month_picker(state, bot, message.chat.id, command.command, new=True)


@router.message(Command("activity"))
async def cmd_activity(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    await show_activity(state, bot, message.chat.id, session, new=True)


@router.message(Command("admins"), IsSuperAdmin())
async def cmd_admins(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await delete_message(bot, message.chat.id, message.message_id)
    await show_admin_list(state, bot, message.chat.id, session, new=True)
