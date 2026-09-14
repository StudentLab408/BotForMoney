from aiogram.fsm.state import State, StatesGroup


class AdminProjectEntry(StatesGroup):
    choosing_student = State()
    waiting_project_name = State()
    waiting_regalia = State()
    confirm = State()
