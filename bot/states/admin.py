from aiogram.fsm.state import State, StatesGroup


class AdminReject(StatesGroup):
    waiting_reason = State()


class AdminCancelAward(StatesGroup):
    waiting_reason = State()


class StudentSearch(StatesGroup):
    waiting_query = State()


class AdminAward(StatesGroup):
    choosing_event = State()
    choosing_participation = State()
    searching_event = State()
    waiting_new_event_name = State()
    waiting_new_event_date = State()
    waiting_details = State()
    choosing_amount = State()
    confirm = State()


class ProjectForm(StatesGroup):
    waiting_name = State()
    waiting_regalia = State()


class EventForm(StatesGroup):
    waiting_name = State()
    waiting_date = State()


class ReportMonth(StatesGroup):
    waiting_custom_month = State()
