from aiogram.fsm.state import State, StatesGroup


class AdminReject(StatesGroup):
    waiting_reason = State()
