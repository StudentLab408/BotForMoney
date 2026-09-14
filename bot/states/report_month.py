from aiogram.fsm.state import State, StatesGroup


class ReportMonth(StatesGroup):
    waiting_custom_month = State()
