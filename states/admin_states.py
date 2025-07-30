"""
Состояния FSM для административных функций
"""

from aiogram.fsm.state import State, StatesGroup


class DeleteRequest(StatesGroup):
    waiting_for_request_id = State()


class AddUser(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_fio = State()
    waiting_for_position = State()


class AssignRole(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_role = State()


class RemoveUser(StatesGroup):
    waiting_for_user_id = State()


class Notify(StatesGroup):
    waiting_for_notification = State() 