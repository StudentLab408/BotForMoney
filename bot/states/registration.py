from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_last_name = State()
    waiting_first_name = State()
    waiting_middle_name = State()
    waiting_group = State()
    confirm = State()
