from aiogram.fsm.state import State, StatesGroup


class Submission(StatesGroup):
    choosing_event = State()
    choosing_participation = State()
    searching_event = State()
    waiting_new_event_name = State()
    waiting_new_event_date = State()
    waiting_details = State()
    confirm = State()
