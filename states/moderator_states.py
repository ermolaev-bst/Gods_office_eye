"""
Состояния FSM для модераторских функций
"""

from aiogram.fsm.state import State, StatesGroup


class Moderator(StatesGroup):
    waiting_for_news = State()


class ScheduleMonth(StatesGroup):
    waiting_for_schedule = State() 