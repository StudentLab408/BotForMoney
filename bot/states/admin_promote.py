from aiogram.fsm.state import State, StatesGroup


class AdminPromote(StatesGroup):
    waiting_target = State()
    confirm = State()
