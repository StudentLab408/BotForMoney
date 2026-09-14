from aiogram.fsm.state import State, StatesGroup


class Submission(StatesGroup):
    choosing_type = State()
    waiting_conference_name = State()
    waiting_conference_project_name = State()
    waiting_event_name = State()
    waiting_event_what_did = State()
    confirm = State()
