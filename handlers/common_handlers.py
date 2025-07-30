"""
Общие обработчики для всех пользователей
"""

import logging
from aiogram import types, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_ID, MODERATOR_ID, MARKETER_ID
from database import *
from keyboards import *
from states import AuthorizeUser
from utils import escape_html

logger = logging.getLogger(__name__)


async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    user_id = message.from_user.id
    
    logger.info(f"Команда /start от пользователя {user_id}")
    
    # Проверяем авторизацию
    if await is_authorized(user_id):
        await send_main_menu(message, user_id)
    else:
        # Проверяем, есть ли уже заявка
        existing_request = await get_auth_request_by_user_id(user_id)
        
        if existing_request:
            await message.answer(
                "⏳ Ваша заявка на авторизацию уже отправлена и ожидает рассмотрения.\n"
                "Пожалуйста, дождитесь ответа от администратора."
            )
        else:
            await message.answer(
                "👋 Добро пожаловать!\n\n"
                "Для доступа к функциям бота необходимо пройти авторизацию.\n"
                "Пожалуйста, введите ваше ФИО:"
            )
            await state.set_state(AuthorizeUser.waiting_for_fio)


async def send_main_menu(message: types.Message, user_id: int):
    """Отправляет главное меню в зависимости от роли пользователя"""
    user_role = await get_user_role(user_id)
    
    if user_id == ADMIN_ID:
        keyboard = create_admin_panel_keyboard()
        text = "⚙️ <b>Панель администратора</b>\n\nВыберите действие:"
    elif user_id == MODERATOR_ID:
        keyboard = create_moderator_panel_keyboard()
        text = "🛡️ <b>Панель модератора</b>\n\nВыберите действие:"
    elif user_id == MARKETER_ID or user_role == 'marketer' or (user_id == ADMIN_ID):
        # Администратор также может видеть панель маркетолога
        keyboard = create_marketer_keyboard()
        text = "📢 <b>Панель маркетолога</b>\n\nВыберите действие:"
    else:
        keyboard = create_user_functions_keyboard()
        text = "👤 <b>Главное меню</b>\n\nВыберите действие:"
    
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def back_to_main_callback(callback_query: types.CallbackQuery):
    """Обработчик возврата в главное меню"""
    await send_main_menu(callback_query.message, callback_query.from_user.id)
    await callback_query.answer()


async def help_command(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
🤖 <b>Справка по боту</b>

<b>Основные функции:</b>
• 🔍 Поиск сотрудников по различным критериям
• 📥 Скачивание базы контактов
• 📝 Предложение новостей
• 📅 Просмотр графика кофе

<b>Команды:</b>
• /start - Запуск бота
• /help - Эта справка
• /cancel - Отмена текущего действия

<b>Роли:</b>
• 👤 Пользователь - базовые функции
• 🛡️ Модератор - управление графиком
• 📢 Маркетолог - управление новостями
• 👑 Администратор - полный доступ

При возникновении проблем обратитесь к администратору.
    """
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)


async def cancel_command(message: types.Message, state: FSMContext):
    """Обработчик команды /cancel"""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("Нет активных действий для отмены.")
        return
    
    await state.clear()
    await message.answer("❌ Действие отменено.")
    
    # Отправляем главное меню
    user_id = message.from_user.id
    if await is_authorized(user_id):
        await send_main_menu(message, user_id)


def register_common_handlers(dp: Dispatcher):
    """Регистрирует общие обработчики"""
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(cancel_command, Command("cancel"))
    
    dp.callback_query.register(
        back_to_main_callback,
        lambda c: c.data == "back_to_main"
    ) 