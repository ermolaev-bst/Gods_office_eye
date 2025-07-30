"""
Состояния FSM для пользователей
"""

from aiogram.fsm.state import State, StatesGroup


class AuthorizeUser(StatesGroup):
    waiting_for_fio = State()
    waiting_for_position = State()


class ProposeNews(StatesGroup):
    waiting_for_news = State()


class MessageUser(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()


class Search(StatesGroup):
    waiting_for_fio = State()
    waiting_for_position = State()
    waiting_for_department = State()
    waiting_for_phone = State() 