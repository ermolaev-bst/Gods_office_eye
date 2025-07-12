import asyncio
import logging
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiofiles
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import aiohttp
from config import *
from database import Database
from inline_keyboards import BeautifulInlineKeyboards
from bitrix24_sync import sync_bitrix24_to_excel, get_sync_status

# Импорт веб-интерфейса (Flask)
from moderator_web import run_flask

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info('=== BOT_OFFICE/BOT.PY STARTED ===')



def escape_html(text):
    """Экранирует HTML-символы в тексте"""
    if text is None:
        return 'Не указано'
    
    text_str = str(text)
    
    # Логируем проблемные символы для отладки
    if any(char in text_str for char in ['<', '>', '&']):
        logger.warning(f"Найдены HTML-символы в тексте: {repr(text_str)}")
    
    # Экранируем HTML-символы
    escaped = text_str.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
    
    # Дополнительно экранируем кавычки для безопасности
    escaped = escaped.replace('"', '&quot;').replace("'", '&#39;')
    
    return escaped



# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация менеджера данных
data_manager = DataManager(EXCEL_FILE)

# Состояния FSM
class AuthRequest(StatesGroup):
    waiting_for_fio = State()
    waiting_for_position = State()

class Search(StatesGroup):
    waiting_for_fio = State()
    waiting_for_position = State()
    waiting_for_department = State()
    waiting_for_phone = State()

class RemoveUser(StatesGroup):
    waiting_for_user_id = State()

class Moderator(StatesGroup):
    waiting_for_news = State()

class AssignRole(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_role = State()

class Notify(StatesGroup):
    waiting_for_notification = State()

class ScheduleMonth(StatesGroup):
    waiting_for_schedule = State()

class CoffeeSchedule(StatesGroup):
    waiting_for_schedule = State()

class ChannelSubscribe(StatesGroup):
    waiting_for_fio = State()

class NewsProposal(StatesGroup):
    waiting_for_text = State()
    waiting_for_photos = State()

class EditNewsProposal(StatesGroup):
    waiting_for_text = State()
    waiting_for_photos = State()

class CommentNews(StatesGroup):
    waiting_for_comment = State()

# Вспомогательные функции
async def send_main_menu(message, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    
    is_auth = await is_authorized(user_id)
    if is_auth:
        role = await get_user_role(user_id)
        
        # Главное меню для авторизованного пользователя - сразу показываем функции пользователя
        keyboard = BeautifulInlineKeyboards.create_user_functions_keyboard()
        
        # Добавляем дополнительные панели в зависимости от роли
        if role in ['admin', 'moderator']:
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="🛡️ Панель модератора", callback_data="moderator_panel")])
        if role == 'admin':
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel")])
        if role == 'marketer':
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="📢 Панель маркетолога", callback_data="marketer_panel")])
        
        welcome_text = f"🏢 Корпоративный бот\n\nДобро пожаловать! Ваша роль: {role.capitalize()}\n\nВыберите действие:"
        await message.answer(welcome_text, reply_markup=keyboard)
    else:
        # Показываем приглашение к авторизации
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🔐 Запросить авторизацию", callback_data="request_auth"))
        keyboard.add(InlineKeyboardButton(text="📢 Подписаться на канал", callback_data="channel_subscribe"))
        keyboard.add(InlineKeyboardButton(text="📋 Информация о боте", callback_data="bot_info"))
        keyboard.add(InlineKeyboardButton(text="🧪 Тест callback", callback_data="test_callback"))
        keyboard.adjust(1, 1, 1, 1)
        await message.answer(
            "👋 Добро пожаловать в корпоративный бот!\n\n"
            "Для использования функций необходимо авторизоваться.",
            reply_markup=keyboard.as_markup()
        )

def format_employee_caption(row):
    # нормализуем короткий номер
    short_number = format_short_number(getattr(row, 'Короткий номер', ''))
    # Поиск email по разным вариантам
    email = None
    for key in ['Email', 'E-mail', 'email', 'Почта']:
        if hasattr(row, key):
            email = getattr(row, key)
            if pd.notna(email) and str(email).strip():
                break
    if not email or str(email).strip().lower() in ('nan', 'none', ''):
        email = 'Н/Д'
    caption = (
        f"👤 <b>{getattr(row, 'ФИО', 'Н/Д')}</b>\n"
        f"🏢 <b>Должность:</b> {getattr(row, 'Должность', 'Н/Д')}\n"
        f"📞 <b>Телефон:</b> {getattr(row, 'Телефон', 'Н/Д')}\n"
        f"📱 <b>Короткий:</b> {short_number}\n"
        f"🏢 <b>Отдел:</b> {getattr(row, 'Отдел', 'Н/Д')}\n"
        f"📧 <b>Email:</b> {email}"
    )
    return caption

def format_short_number(value):
    if pd.isna(value) or value == '':
        return 'Н/Д'
    # Если float и целое, выводим как int
    try:
        fval = float(value)
        if fval.is_integer():
            return str(int(fval))
        return str(fval)
    except Exception:
        return str(value)

def require_roles(*roles):
    def decorator(func):
        async def wrapper(message: types.Message, *args, **kwargs):
            user_id = message.from_user.id
            if not await is_authorized(user_id):
                await message.answer("Для использования этой функции необходимо авторизоваться.")
                return
            user_role = await get_user_role(user_id)
            if user_role not in roles:
                await message.answer("У вас нет прав для использования этой функции.")
                return
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

# Основные обработчики команд
@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_before_clear={current_state}")
    await state.clear()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_after_clear={await state.get_state()}")
    await send_main_menu(message)

def normalize_fio(fio: str) -> str:
    """Нормализует ФИО: нижний регистр, заменяет ё на е, убирает лишние пробелы"""
    return fio.lower().replace('ё', 'е').replace('Ё', 'Е').strip()

# Обработчик получения ФИО от пользователя (для заявок на вступление в канал)
@dp.message(ChannelSubscribe.waiting_for_fio)
async def handle_fio_input(message: types.Message, state: FSMContext):
    """Обработчик получения ФИО от пользователя для заявки на вступление в канал"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        fio = message.text.strip()
        
        # Проверяем, что мы действительно в состоянии ожидания ФИО для канала
        current_state = await state.get_state()
        current_data = await state.get_data()
        logger.info(f"[CHANNEL_FIO] user_id={user_id}, state={current_state}, data={current_data}, text={fio}")
        
        # Проверяем флаг pending_channel_request
        data = await state.get_data()
        is_pending_request = data.get('pending_channel_request', False)
        if not is_pending_request:
            logger.warning(f"[CHANNEL_FIO] No pending_channel_request flag for user_id={user_id}")
            await state.clear()
            return
        
        if not fio or len(fio) < 3:
            await message.answer(
                "❌ <b>Неверный формат ФИО</b>\n\n"
                "Пожалуйста, отправьте ваше полное имя (Фамилия Имя Отчество).\n"
                "Минимальная длина: 3 символа.",
                parse_mode=ParseMode.HTML
            )
            return
        
        logger.info(f"Получено ФИО от пользователя для канала: user_id={user_id}, fio={fio}")
        
        # Проверяем, есть ли уже подписчик с таким ФИО
        if await is_fio_already_subscribed(fio):
            existing_subscriber = await get_subscriber_by_fio(fio)
            if existing_subscriber:
                existing_user_id = existing_subscriber[0]
                logger.warning(f"Дублирование ФИО: {fio} уже подписан как user_id={existing_user_id}, новый user_id={user_id}")
                await message.answer(
                    f"❌ <b>Заявка на вступление в канал отклонена</b>\n\n"
                    f"👤 <b>ФИО:</b> {fio}\n\n"
                    f"<b>Причина:</b> Пользователь с таким ФИО уже подписан на канал.\n\n"
                    f"Если это ошибка, обратитесь к администратору.",
                    parse_mode=ParseMode.HTML
                )
                admin_message = (
                    f"❌ <b>Отклонена заявка на вступление (дублирование ФИО)</b>\n\n"
                    f"👤 <b>ФИО:</b> {fio}\n"
                    f"🆔 <b>Новый ID:</b> {user_id}\n"
                    f"👤 <b>Существующий ID:</b> {existing_user_id}\n"
                    f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"❌ <b>Статус:</b> Отклонена (дублирование ФИО)"
                )
                await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
                await state.clear()
                await send_main_menu(message, user_id=user_id)
                return
        
        import pandas as pd
        import os
        if not CHANNEL_USERS_EXCEL or not os.path.exists(CHANNEL_USERS_EXCEL):
            logger.warning("Excel файл канала недоступен для проверки")
            await message.answer(
                f"❌ <b>Заявка на вступление в канал отклонена</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n\n"
                f"<b>Причина:</b> Система проверки недоступна.\n\n"
                f"Обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )
            await state.clear()
            await send_main_menu(message, user_id=user_id)
            return
        try:
            df = pd.read_excel(CHANNEL_USERS_EXCEL)
            logger.info(f"Channel Excel loaded: {len(df)} rows for FIO check")
        except Exception as e:
            logger.error(f"Ошибка чтения Excel файла канала: {e}")
            await message.answer(
                f"❌ <b>Ошибка проверки</b>\n\n"
                f"Произошла ошибка при проверке вашего ФИО.\n\n"
                f"Обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )
            await state.clear()
            await send_main_menu(message, user_id=user_id)
            return
        fio_column = None
        for col in df.columns:
            if 'фио' in col.lower():
                fio_column = col
                break
        if fio_column is None:
            fio_column = df.columns[0]
            logger.warning(f"Колонка с ФИО не найдена, используем: {fio_column}")
        user_found = False
        user_fio_norm = normalize_fio(fio)
        for idx, row in df.iterrows():
            excel_fio = str(row[fio_column]).strip()
            if normalize_fio(excel_fio) == user_fio_norm:
                user_found = True
                logger.info(f"Пользователь найден в Excel: {fio} (строка {idx + 1})")
                break
        if user_found:
            await add_channel_subscriber(user_id, username, fio)
            await message.answer(
                f"✅ <b>Заявка на вступление в канал одобрена!</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"👤 <b>Username:</b> @{username or 'Нет'}\n\n"
                f"Добро пожаловать в канал!",
                parse_mode=ParseMode.HTML
            )
            admin_message = (
                f"✅ <b>Одобрена заявка на вступление в канал</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"👤 <b>Username:</b> @{username or 'Нет'}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"✅ <b>Статус:</b> Автоматически одобрена (найден в Excel)"
            )
            await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
            logger.info(f"Channel join request approved: user_id={user_id}, fio={fio}")
        else:
            await message.answer(
                f"❌ <b>Заявка на вступление в канал отклонена</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n\n"
                f"<b>Причина:</b> Ваше ФИО не найдено в списке разрешенных пользователей.\n\n"
                f"Если вы считаете, что это ошибка, обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )
            admin_message = (
                f"❌ <b>Отклонена заявка на вступление в канал</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"👤 <b>Username:</b> @{username or 'Нет'}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"❌ <b>Статус:</b> Автоматически отклонена (не найден в Excel)"
            )
            await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
            logger.info(f"Channel join request rejected: user_id={user_id}, fio={fio}")
        
        await state.clear()
        await send_main_menu(message, user_id=user_id)
        
    except Exception as e:
        logger.error(f"Ошибка обработки ФИО от пользователя {message.from_user.id}: {e}")
        await message.answer("Произошла ошибка при обработке вашего ФИО. Попробуйте позже.")
        await state.clear()
        await send_main_menu(message, user_id=message.from_user.id)

@dp.message(Command("channel_subscribe"))
async def channel_subscribe_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Введите ФИО для поиска сотрудника:")
    await state.set_state(Search.waiting_for_fio)

@dp.message(Command("menu"))
async def show_menu(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_before_clear={current_state}")
    await state.clear()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_after_clear={await state.get_state()}")
    await send_main_menu(message)

@dp.message(F.text.lower().in_(["меню", "menu", "главное меню", "главная"]))
async def show_menu_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_before_clear={current_state}")
    await state.clear()
    logger.info(f"[MENU] user_id={message.from_user.id}, state_after_clear={await state.get_state()}")
    await send_main_menu(message)

# Обработчики callback'ов
@dp.callback_query(lambda c: c.data == "test_callback")
async def test_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Тестовый callback работает!", show_alert=True)

@dp.callback_query(lambda c: c.data == "request_auth")
async def request_auth_callback(callback_query: types.CallbackQuery, state: FSMContext):
    is_auth = await is_authorized(callback_query.from_user.id)
    
    if is_auth:
        await callback_query.answer("Вы уже авторизованы!", show_alert=True)
        await send_main_menu(callback_query.message, user_id=callback_query.from_user.id)
        return
    
    await callback_query.answer()
    await callback_query.message.answer(
        "👋 <b>Авторизация в корпоративном боте</b>\n\n"
        "Для использования функций необходимо авторизоваться.\n\n"
        "Пожалуйста, введите ваше ФИО (Фамилия Имя Отчество):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AuthRequest.waiting_for_fio)

@dp.callback_query(lambda c: c.data == "bot_info")
async def bot_info_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await callback_query.message.answer(
        "ℹ️ <b>Информация о боте</b>\n\n"
        "🤖 <b>Корпоративный бот</b>\n"
        "📋 <b>Функции:</b>\n"
        "• Поиск сотрудников\n"
        "• Управление новостями\n"
        "• График кофе\n"
        "• Административные функции\n\n"
        "🔐 Для доступа к функциям необходимо авторизоваться.",
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(lambda c: c.data == "channel_subscribe")
async def channel_subscribe_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer("Введите ФИО для поиска сотрудника:")
    await state.set_state(Search.waiting_for_fio)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_callback(callback_query: types.CallbackQuery):
    await send_main_menu(callback_query.message, user_id=callback_query.from_user.id)



@dp.callback_query(lambda c: c.data == "moderator_panel")
async def moderator_panel_callback(callback_query: types.CallbackQuery):
    keyboard = BeautifulInlineKeyboards.create_moderator_panel_keyboard()
    await callback_query.message.edit_text(
        "🛡️ Панель модератора\n\nВыберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "marketer_panel")
async def marketer_panel_callback(callback_query: types.CallbackQuery):
    keyboard = BeautifulInlineKeyboards.create_marketer_keyboard()
    await callback_query.message.edit_text(
        "📢 Панель маркетолога\n\nВыберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "admin_panel")
async def admin_panel_callback(callback_query: types.CallbackQuery):
    keyboard = BeautifulInlineKeyboards.create_admin_panel_keyboard()
    await callback_query.message.edit_text(
        "👑 Админ панель\n\nВыберите действие:",
            reply_markup=keyboard
        )

# Обработчики для одобрения/отклонения новостей
@dp.callback_query(lambda c: c.data and c.data.startswith("approve_news_"))
async def approve_news_callback(callback_query: types.CallbackQuery):
    logger.debug(f"DEBUG_CALLBACK: approve_news received from user {callback_query.from_user.id}")
    logger.debug(f"DEBUG_CALLBACK: callback_data='{callback_query.data}'")
    print(f"DEBUG: approve_news callback received: {callback_query.data}")
    
    logger.debug(f"CALLBACK: approve_news from user {callback_query.from_user.id}")
    logger.debug(f"CALLBACK: approve_news callback_data={callback_query.data}")
    print("approve_news_callback called!", callback_query.data)
    await callback_query.answer("approve_news_callback!", show_alert=True)
    
    # Проверяем, что callback_data имеет правильный формат
    parts = callback_query.data.split("_")
    if len(parts) < 3:
        logger.error(f"CALLBACK: Invalid callback_data format: {callback_query.data}")
        await callback_query.answer("Ошибка: неверный формат callback_data", show_alert=True)
        return
    
    try:
        proposal_id = int(parts[2])
        if proposal_id <= 0:
            logger.error(f"CALLBACK: Invalid proposal_id: {proposal_id}")
            await callback_query.answer("Ошибка: неверный ID предложения", show_alert=True)
            return
    except ValueError as e:
        logger.error(f"CALLBACK: Error parsing proposal_id from {parts[2]}: {e}")
        await callback_query.answer("Ошибка: неверный ID предложения", show_alert=True)
        return
    
    logger.info(f"[approve_news_callback] called for proposal_id={proposal_id}, by user_id={callback_query.from_user.id}")
    import traceback
    
    try:
        # Получаем предложение
        proposal = await get_news_proposal_by_id(proposal_id)
        logger.info(f"[approve_news_callback] proposal from DB: {proposal}")
        if not proposal:
            logger.warning(f"[approve_news_callback] proposal_id={proposal_id} not found!")
            await callback_query.answer("Предложение не найдено.")
            return
        
        proposal_id, user_id, username, fio, news_text, photos_json, status, marketer_id, comment, created_at, processed_at = proposal
        logger.info(f"[approve_news_callback] status={status}, user_id={user_id}, fio={fio}, marketer_id={marketer_id}")
        if status != 'pending':
            logger.warning(f"[approve_news_callback] proposal_id={proposal_id} already processed (status={status})")
            await callback_query.answer("Это предложение уже обработано.")
            return
        
        # Обновляем статус
        await update_news_proposal_status(proposal_id, 'approved', callback_query.from_user.id, "Одобрено")
        logger.info(f"[approve_news_callback] status updated in DB for proposal_id={proposal_id}")
        
        # Публикуем в канал
        import json
        photos = json.loads(photos_json) if photos_json else []
        logger.info(f"[approve_news_callback] CHANNEL_CHAT_ID={CHANNEL_CHAT_ID}, photos_count={len(photos)}")
        
        try:
            if photos:
                # Отправляем с фотографиями
                media_group = []
                for i, photo_id in enumerate(photos):
                    if i == 0:
                        media_group.append(types.InputMediaPhoto(
                            media=photo_id,
                            caption=f"�� <b>Новость от {fio}</b>\n\n{news_text}" if i == 0 else None,
                            parse_mode=ParseMode.HTML
                        ))
                    else:
                        media_group.append(types.InputMediaPhoto(media=photo_id))
                logger.info(f"[approve_news_callback] Sending media_group to channel {CHANNEL_CHAT_ID}")
                await bot.send_media_group(CHANNEL_CHAT_ID, media_group)
            else:
                logger.info(f"[approve_news_callback] Sending text message to channel {CHANNEL_CHAT_ID}")
                await bot.send_message(
                    CHANNEL_CHAT_ID,
                    f"�� <b>Новость от {fio}</b>\n\n{news_text}",
                    parse_mode=ParseMode.HTML
                )
            
            # Уведомляем автора
            logger.info(f"[approve_news_callback] Notifying author user_id={user_id}")
            await bot.send_message(
                user_id,
                f"✅ Ваша новость одобрена и опубликована в канале!"
            )
            
            # Обновляем сообщение маркетолога
            logger.info(f"[approve_news_callback] Editing message for marketer (proposal_id={proposal_id})")
            await callback_query.message.edit_text(
                f"✅ Предложение #{proposal_id} одобрено и опубликовано.",
                reply_markup=None
            )
            await callback_query.answer("Новость опубликована в канале!", show_alert=True)
            logger.info(f"[approve_news_callback] Success for proposal_id={proposal_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при публикации новости в канал: {e}\n{traceback.format_exc()}")
            await callback_query.message.answer(f"❌ Ошибка при публикации новости в канал: {e}")
            await callback_query.answer("Ошибка при публикации новости!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка при одобрении новости: {e}\n{traceback.format_exc()}")
        await callback_query.answer("Произошла ошибка при одобрении новости.")

@dp.callback_query(lambda c: c.data and c.data.startswith("reject_news_"))
async def reject_news_callback(callback_query: types.CallbackQuery):
    logger.debug(f"DEBUG_CALLBACK: reject_news received from user {callback_query.from_user.id}")
    logger.debug(f"DEBUG_CALLBACK: callback_data='{callback_query.data}'")
    print(f"DEBUG: reject_news callback received: {callback_query.data}")
    
    logger.debug(f"CALLBACK: reject_news from user {callback_query.from_user.id}")
    proposal_id = int(callback_query.data.split("_")[-1])
    logger.info(f"[reject_news_callback] called for proposal_id={proposal_id}, by user_id={callback_query.from_user.id}")
    
    try:
        proposal = await get_news_proposal_by_id(proposal_id)
        if not proposal:
            await callback_query.answer("Предложение не найдено.")
            return
        
        proposal_id, user_id, username, fio, news_text, photos_json, status, marketer_id, comment, created_at, processed_at = proposal
        if status != 'pending':
            await callback_query.answer("Это предложение уже обработано.")
            return
        
        await update_news_proposal_status(proposal_id, 'rejected', callback_query.from_user.id, "Отклонено")
        
        # Уведомить автора (обработка ошибки)
        try:
            await bot.send_message(user_id, "❌ Ваша новость отклонена маркетологом.")
        except Exception as e:
            logger.error(f"Ошибка при уведомлении пользователя {user_id}: {e}")
        
        await callback_query.message.edit_text(f"❌ Предложение #{proposal_id} отклонено.", reply_markup=None)
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении новости: {e}")
        await callback_query.answer("Ошибка при отклонении новости.")

# Обработчики для одобрения/отклонения пользователей
@dp.callback_query(lambda c: c.data and c.data.startswith("approve_"))
async def process_approve(callback_query: types.CallbackQuery):
    logger.debug(f"DEBUG_CALLBACK: approve received from user {callback_query.from_user.id}")
    logger.debug(f"DEBUG_CALLBACK: callback_data='{callback_query.data}'")
    print(f"DEBUG: approve callback received: {callback_query.data}")
    
    parts = callback_query.data.split("_")
    
    # Проверяем, что это не approve_news_
    if len(parts) >= 2 and parts[1] == "news":
        logger.debug(f"CALLBACK: approve_news detected, skipping user approval handler for {callback_query.data}")
        # Не обрабатываем approve_news_... этим обработчиком
        return

    if len(parts) == 2 and parts[1].isdigit():
        user_id = int(parts[1])
        logger.debug(f"CALLBACK: approve user {user_id} by admin {callback_query.from_user.id}")
        
        try:
            # Одобряем пользователя в базе данных
            await approve_user(user_id)
            
            # Отправляем уведомление пользователю с клавиатурой
            await bot.send_message(user_id, "✅ Ваша заявка одобрена! Теперь вы можете использовать бота.")
            
            # Отправляем главное меню с клавиатурой
            try:
                await send_main_menu(types.Message(
                    message_id=0,
                    date=datetime.now(),
                    chat=types.Chat(id=user_id, type="private"),
                    from_user=types.User(id=user_id, is_bot=False, first_name="User")
                ), user_id=user_id)
            except Exception as e:
                logger.error(f"Ошибка при отправке меню пользователю {user_id}: {e}")
            
            # Обновляем сообщение администратора
            await callback_query.message.edit_text(
                f"✅ Пользователь {user_id} одобрен.",
                reply_markup=None
            )
            
            # Логируем действие
            await log_admin_action(callback_query.from_user.id, f"Одобрил пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при одобрении пользователя {user_id}: {e}")
            await callback_query.answer("Произошла ошибка при одобрении пользователя.")
    else:
        # Не обрабатываем другие форматы approve_
        return

@dp.callback_query(lambda c: c.data and c.data.startswith("decline_"))
async def process_decline(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    logger.debug(f"CALLBACK: decline user {user_id} by admin {callback_query.from_user.id}")
    
    try:
        # Удаляем заявку из базы данных
        await remove_user(user_id)
        
        # Отправляем уведомление пользователю
        await bot.send_message(user_id, "❌ Ваша заявка отклонена. Обратитесь к администратору для уточнения деталей.")
        
        # Обновляем сообщение администратора
        await callback_query.message.edit_text(
            f"❌ Пользователь {user_id} отклонен.",
            reply_markup=None
        )
        
        # Логируем действие
        await log_admin_action(callback_query.from_user.id, f"Отклонил пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении пользователя {user_id}: {e}")
        await callback_query.answer("Произошла ошибка при отклонении пользователя.")

# Обработчики состояний авторизации
@dp.message(AuthRequest.waiting_for_fio)
async def process_fio(message: types.Message, state: FSMContext):
    fio = message.text.strip()
    
    # Проверяем формат ФИО
    if not fio or len(fio) < 3:
        await message.answer(
            "❌ <b>Неверный формат ФИО</b>\n\n"
            "Пожалуйста, введите ваше полное имя (Фамилия Имя Отчество).\n"
            "Минимальная длина: 3 символа.",
            parse_mode=ParseMode.HTML
        )
        return
    
    await state.update_data(fio=fio)
    await message.answer(
        "✅ <b>ФИО принято!</b>\n\n"
        f"👤 <b>Ваше ФИО:</b> {fio}\n\n"
        "Теперь введите вашу должность:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AuthRequest.waiting_for_position)

@dp.message(AuthRequest.waiting_for_position)
async def process_position(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fio = data.get('fio')
    position = message.text.strip()
    
    if not position or len(position) < 2:
        await message.answer(
            "❌ <b>Неверный формат должности</b>\n\n"
            "Пожалуйста, введите вашу должность.\n"
            "Минимальная длина: 2 символа.",
            parse_mode=ParseMode.HTML
        )
        return
    
    logger.info(f"Обработка авторизации: user_id={message.from_user.id}, fio={fio}, position={position}")
    
    # Проверяем ФИО в Excel файле канала
    import pandas as pd
    import os
    
    user_found_in_excel = False
    
    if CHANNEL_USERS_EXCEL and os.path.exists(CHANNEL_USERS_EXCEL):
        try:
            df = pd.read_excel(CHANNEL_USERS_EXCEL)
            logger.info(f"Excel файл канала загружен: {len(df)} строк для проверки авторизации")
            
            # Ищем колонку с ФИО
            fio_column = None
            for col in df.columns:
                if 'фио' in col.lower():
                    fio_column = col
                    break
            
            if fio_column is None:
                fio_column = df.columns[0]
                logger.warning(f"Колонка с ФИО не найдена, используем: {fio_column}")
            
            # Ищем пользователя в Excel
            user_fio_norm = normalize_fio(fio)
            for idx, row in df.iterrows():
                excel_fio = str(row[fio_column]).strip()
                if normalize_fio(excel_fio) == user_fio_norm:
                    user_found_in_excel = True
                    logger.info(f"Пользователь найден в Excel для авторизации: {fio} (строка {idx + 1})")
                    break
                    
        except Exception as e:
            logger.error(f"Ошибка чтения Excel файла канала при авторизации: {e}")
    
    if user_found_in_excel:
        # Пользователь найден в Excel - автоматически одобряем
        try:
            # Добавляем пользователя в базу данных как авторизованного
            await approve_user(message.from_user.id)
            
            # Добавляем информацию о пользователе
            await add_auth_request(message.from_user.id, message.from_user.username, fio, position)
            
            # Уведомляем пользователя
            await message.answer(
                f"✅ <b>Авторизация одобрена автоматически!</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"💼 <b>Должность:</b> {position}\n"
                f"🆔 <b>ID:</b> {message.from_user.id}\n\n"
                f"Добро пожаловать в корпоративный бот!",
                parse_mode=ParseMode.HTML
            )
            
            # Показываем главное меню
            await send_main_menu(message)
            
            # Уведомляем администратора
            admin_message = (
                f"✅ <b>Автоматически одобрена авторизация</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"💼 <b>Должность:</b> {position}\n"
                f"🆔 <b>ID:</b> {message.from_user.id}\n"
                f"👤 <b>Username:</b> @{message.from_user.username or 'Нет'}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"✅ <b>Статус:</b> Автоматически одобрена (найден в Excel канала)"
            )
            
            await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
            logger.info(f"Авторизация автоматически одобрена: user_id={message.from_user.id}, fio={fio}")
            
        except Exception as e:
            logger.error(f"Ошибка автоматического одобрения авторизации: {e}")
            await message.answer("Произошла ошибка при авторизации. Попробуйте позже.")
            
    else:
        # Пользователь не найден в Excel - отправляем на рассмотрение администратору
        try:
            # Добавляем заявку в базу данных
            await add_auth_request(message.from_user.id, message.from_user.username, fio, position)
            
            # Уведомляем пользователя
            await message.answer(
                f"⏳ <b>Заявка отправлена на рассмотрение</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"💼 <b>Должность:</b> {position}\n"
                f"🆔 <b>ID:</b> {message.from_user.id}\n\n"
                f"Ваша заявка отправлена администратору. Ожидайте ответа.",
                parse_mode=ParseMode.HTML
            )
            
            # Уведомляем администратора
            admin_message = (
                f"🔔 <b>Новая заявка на авторизацию</b>\n\n"
                f"👤 <b>ФИО:</b> {fio}\n"
                f"💼 <b>Должность:</b> {position}\n"
                f"🆔 <b>ID:</b> {message.from_user.id}\n"
                f"👤 <b>Username:</b> @{message.from_user.username or 'Нет'}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"❌ <b>Статус:</b> Не найден в Excel канала - требует рассмотрения"
            )
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{message.from_user.id}"))
            keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{message.from_user.id}"))
            keyboard.adjust(2)
            
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
            logger.info(f"Заявка на авторизацию отправлена администратору: user_id={message.from_user.id}, fio={fio}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки заявки на авторизацию: {e}")
            await message.answer("Произошла ошибка при отправке заявки. Попробуйте позже.")
    
    await state.clear()

# Обработчики функций пользователя
@dp.callback_query(lambda c: c.data == "search_employees")
async def search_employees_callback(callback_query: types.CallbackQuery):
    keyboard = BeautifulInlineKeyboards.create_search_keyboard()
    await callback_query.message.edit_text(
        "🔍 Поиск сотрудника\n\nВыберите тип поиска:",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "search_employee")
async def search_employee_callback(callback_query: types.CallbackQuery):
    keyboard = BeautifulInlineKeyboards.create_search_keyboard()
    await callback_query.message.edit_text(
        "🔍 Поиск сотрудника\n\nВыберите тип поиска:",
        reply_markup=keyboard
    )



@dp.callback_query(lambda c: c.data == "coffee_schedule")
async def coffee_schedule_callback(callback_query: types.CallbackQuery):
    try:
        user_role = await get_user_role(callback_query.from_user.id)
        
        # Если модератор - показываем панель управления графиком
        if user_role == "moderator":
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="📝 Составить график", callback_data="create_coffee_schedule")
            keyboard.button(text="📊 Просмотреть график", callback_data="view_coffee_schedule")
            keyboard.button(text="🗑 Очистить график", callback_data="clear_coffee_schedule")
            keyboard.button(text="🔙 Назад", callback_data="moderator_panel")
            keyboard.adjust(1)
            
            await callback_query.message.edit_text(
                "☕ <b>Управление графиком кофемашины</b>\n\n"
                "Выберите действие:",
                reply_markup=keyboard.as_markup(),
                parse_mode=ParseMode.HTML
            )
        else:
            # Для обычных пользователей - показываем их график
            user_info = await get_user_info(callback_query.from_user.id)
            
            if not user_info:
                logger.warning(f"Пользователь {callback_query.from_user.id} не найден в базе authorized_users")
                await callback_query.message.answer("❌ Вы не авторизованы в системе. Обратитесь к администратору.")
                return
            
            user_fio = user_info[2]  # fio
            logger.info(f"Поиск графика кофе для пользователя {callback_query.from_user.id} с ФИО: {user_fio}")
            
            # Проверяем, есть ли пользователь с таким ФИО в базе авторизованных пользователей
            user_by_fio = await get_user_by_fio(user_fio)
            if not user_by_fio:
                logger.warning(f"Пользователь с ФИО '{user_fio}' не найден в базе авторизованных пользователей")
                await callback_query.message.answer("❌ Ваше ФИО не найдено в базе авторизованных пользователей. Обратитесь к администратору.")
                return
            
            today = datetime.now().strftime("%Y-%m-%d")
            schedule = await get_coffee_schedule_by_fio(user_fio)
            
            logger.info(f"Найдено записей в графике для {user_fio}: {len(schedule) if schedule else 0}")
            
            if not schedule:
                await callback_query.message.answer("☕ У вас нет запланированных дежурств по кофе.")
                return
                
            text = "☕ <b>Ваш график кофе:</b>\n\n"
            future_entries = 0
            
            for entry in schedule:
                # entry[0] = id/rowid, entry[1] = fio, entry[2] = date
                entry_date = entry[2]
                logger.info(f"Проверяем запись: {entry_date} (тип: {type(entry_date)})")
                
                # Проверяем, что дата не None и не пустая
                if entry_date is not None and entry_date != "":
                    try:
                        # Универсальный парсер дат
                        if isinstance(entry_date, str):
                            if '.' in entry_date:
                                parsed_date = datetime.strptime(entry_date, "%d.%m.%Y")
                            elif '-' in entry_date:
                                try:
                                    parsed_date = datetime.strptime(entry_date, "%d-%m-%Y")
                                except ValueError:
                                    parsed_date = datetime.strptime(entry_date, "%Y-%m-%d")
                            else:
                                raise ValueError("Неизвестный формат даты")
                        else:
                            raise ValueError("Дата не строка")
                        
                        today_date = datetime.strptime(today, "%Y-%m-%d")
                        
                        if parsed_date >= today_date:
                            text += f"📅 {entry_date}\n"
                            future_entries += 1
                            logger.info(f"✅ Запись {entry_date} включена (>= {today})")
                        else:
                            logger.info(f"❌ Запись {entry_date} исключена (< {today})")
                            
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге даты {entry_date}: {e}")
                        continue
            
            logger.info(f"Найдено {future_entries} будущих записей для {user_fio}")
            
            if future_entries == 0:
                await callback_query.message.answer("☕ У вас нет запланированных дежурств по кофе.")
            else:
                await callback_query.message.answer(text, parse_mode=ParseMode.HTML)
        
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при просмотре графика кофе: {e}")
        await callback_query.answer("Произошла ошибка при просмотре графика кофе.", show_alert=True)

@dp.callback_query(lambda c: c.data == "propose_news")
async def propose_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📝 Введите текст новости, которую хотите предложить:")
    await state.set_state(NewsProposal.waiting_for_text)
    await callback_query.answer()

# Обработчики поиска
@dp.callback_query(lambda c: c.data == "search_by_fio")
async def search_by_fio_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()  # Сбросить все старые состояния!
    await callback_query.message.answer("Введите ФИО для поиска:")
    await state.set_state(Search.waiting_for_fio)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "search_by_position")
async def search_by_position_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Введите должность для поиска:")
    await state.set_state(Search.waiting_for_position)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "search_by_department")
async def search_by_department_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Введите отдел для поиска:")
    await state.set_state(Search.waiting_for_department)
    await callback_query.answer()

# Обработчики состояний поиска
# Удалено: старые обработчики поиска по ФИО, должности и отделу (без кнопки назад)

# Обработчики панели модератора
@dp.callback_query(lambda c: c.data == "view_news_proposals")
async def view_news_proposals_callback(callback_query: types.CallbackQuery):
    try:
        proposals = await get_pending_news_proposals()
        if not proposals:
            await callback_query.message.answer("📋 Нет предложений новостей для рассмотрения.")
            await callback_query.answer()
            return
        
        for proposal in proposals:
            proposal_id, user_id, username, fio, news_text, photos_json, status, marketer_id, comment, created_at, processed_at = proposal
            
            # Экранируем HTML-символы
            safe_fio = escape_html(fio)
            safe_username = escape_html(username) if username else 'Нет'
            safe_news_text = escape_html(news_text) if news_text else ''
            safe_created_at = escape_html(created_at) if created_at else ''
            
            # Создаем клавиатуру для каждого предложения
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="✅ Одобрить и опубликовать", callback_data=f"approve_news_{proposal_id}"))
            keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_news_{proposal_id}"))
            keyboard.add(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_news_{proposal_id}"))
            keyboard.add(InlineKeyboardButton(text="💬 Добавить комментарий", callback_data=f"comment_news_{proposal_id}"))
            keyboard.adjust(2, 2)
            
            # Формируем текст сообщения
            photos = json.loads(photos_json) if photos_json else []
            photos_text = f"📸 Фотографий: {len(photos)}" if photos else "📸 Без фотографий"
            
            message_text = (
                f"📋 <b>Предложение новости #{proposal_id}</b>\n\n"
                f"👤 <b>Автор:</b> {safe_fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"📝 <b>Username:</b> @{safe_username}\n"
                f"📅 <b>Дата:</b> {safe_created_at}\n"
                f"{photos_text}\n\n"
                f"📄 <b>Текст новости:</b>\n{safe_news_text[:500]}{'...' if len(safe_news_text) > 500 else ''}"
            )
            
            # Отправляем сообщение с фотографиями или без
            if photos:
                media_group = []
                for i, photo_id in enumerate(photos[:10]):  # Ограничиваем 10 фото
                    if i == 0:
                        media_group.append(types.InputMediaPhoto(
                            media=photo_id,
                            caption=message_text,
                            parse_mode=ParseMode.HTML
                        ))
                    else:
                        media_group.append(types.InputMediaPhoto(media=photo_id))
                await callback_query.message.answer_media_group(media_group)
                # Отправляем клавиатуру отдельным сообщением
                await callback_query.message.answer(
                    f"🎛️ <b>Действия для предложения #{proposal_id}</b>",
                    reply_markup=keyboard.as_markup(),
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.message.answer(
                    message_text,
                    reply_markup=keyboard.as_markup(),
                    parse_mode=ParseMode.HTML
                )
        
        await callback_query.answer(f"Найдено {len(proposals)} предложений")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре предложений новостей: {e}")
        await callback_query.answer("Произошла ошибка при загрузке предложений.", show_alert=True)

@dp.callback_query(lambda c: c.data == "view_pending_requests")
async def view_pending_requests_callback(callback_query: types.CallbackQuery):
    try:
        requests = await get_pending_auth_requests()
        if not requests:
            await callback_query.message.answer("📋 Нет заявок на авторизацию.")
            await callback_query.answer()
            return
        
        for request in requests:
            user_id, username, fio, position, created_at = request
            
            # Экранируем HTML-символы
            safe_fio = escape_html(fio)
            safe_username = escape_html(username) if username else 'Нет'
            safe_position = escape_html(position)
            safe_created_at = escape_html(created_at) if created_at else ''
            
            keyboard = InlineKeyboardBuilder()
            keyboard.add(InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"))
            keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{user_id}"))
            keyboard.adjust(2)
            
            message_text = (
                f"🔔 <b>Заявка на авторизацию</b>\n\n"
                f"👤 <b>Пользователь:</b> {safe_fio}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"📝 <b>Username:</b> @{safe_username}\n"
                f"💼 <b>Должность:</b> {safe_position}\n"
                f"📅 <b>Дата:</b> {safe_created_at}"
            )
            
            await callback_query.message.answer(
                message_text,
                reply_markup=keyboard.as_markup(),
                parse_mode=ParseMode.HTML
            )
        
        await callback_query.answer(f"Найдено {len(requests)} заявок")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре заявок: {e}")
        await callback_query.answer("Произошла ошибка при загрузке заявок.", show_alert=True)

# Обработчики админ панели
@dp.callback_query(lambda c: c.data == "view_requests")
async def view_requests_callback(callback_query: types.CallbackQuery):
    await view_pending_requests_callback(callback_query)

@dp.callback_query(lambda c: c.data == "view_users")
async def view_users_callback(callback_query: types.CallbackQuery):
    try:
        logger.info(f"Запрос на просмотр пользователей от {callback_query.from_user.id}")
        users = await get_authorized_users()
        logger.info(f"Получено {len(users)} пользователей из базы данных")
        
        if not users:
            await callback_query.message.answer("�� Нет авторизованных пользователей.")
            await callback_query.answer()
            return

        text = "👥 <b>Авторизованные пользователи:</b>\n\n"
        for i, user in enumerate(users):
            try:
                user_id, username, fio, position, role = user
                
                # Экранируем HTML-символы
                safe_fio = escape_html(fio)
                safe_username = escape_html(username) if username else 'Нет'
                safe_position = escape_html(position)
                safe_role = escape_html(role) if role else 'user'
                
                user_text = f"�� <b>{safe_fio}</b>\n"
                user_text += f"🆔 ID: {user_id}\n"
                user_text += f"�� @{safe_username}\n"
                user_text += f"💼 {safe_position}\n"
                user_text += f"�� Роль: {safe_role}\n\n"
                
                # Проверяем длину текста перед добавлением
                if len(text + user_text) > 4000:  # Оставляем запас
                    logger.info(f"Отправляем первую часть текста длиной {len(text)} символов")
                    await callback_query.message.answer(text, parse_mode=ParseMode.HTML)
                    text = "👥 <b>Авторизованные пользователи (продолжение):</b>\n\n"
                
                text += user_text
                
                # Логируем каждый 10-й пользователя для отладки
                if (i + 1) % 10 == 0:
                    logger.info(f"Обработано {i + 1} пользователей, текущая длина текста: {len(text)}")
                
                # Логируем данные пользователя для отладки (только для первых 5)
                if i < 5:
                    logger.info(f"Пользователь {i+1}: ID={user_id}, FIO='{fio}', Username='{username}', Position='{position}', Role='{role}'")
                    logger.info(f"Экранированные данные: FIO='{safe_fio}', Username='{safe_username}', Position='{safe_position}', Role='{safe_role}'")
                    
            except Exception as user_error:
                logger.error(f"Ошибка обработки пользователя {user}: {user_error}")
                continue
        
        # Проверяем валидность HTML перед отправкой
        def validate_html(text):
            """Проверяет, что HTML-теги правильно закрыты"""
            open_tags = []
            i = 0
            while i < len(text):
                if text[i] == '<':
                    if i + 1 < len(text) and text[i + 1] == '/':
                        # Закрывающий тег
                        end = text.find('>', i)
                        if end == -1:
                            return False, f"Незакрытый тег на позиции {i}"
                        tag = text[i+2:end].strip()
                        if not open_tags or open_tags.pop() != tag:
                            return False, f"Несоответствие тегов: ожидался {open_tags[-1] if open_tags else 'None'}, получен {tag}"
                        i = end + 1
                    else:
                        # Открывающий тег
                        end = text.find('>', i)
                        if end == -1:
                            return False, f"Незакрытый тег на позиции {i}"
                        tag = text[i+1:end].strip()
                        if tag and not tag.startswith('/'):
                            open_tags.append(tag)
                        i = end + 1
                else:
                    i += 1
            return len(open_tags) == 0, None
        
        # Проверяем валидность HTML
        is_valid, error_msg = validate_html(text)
        if not is_valid:
            logger.error(f"Невалидный HTML: {error_msg}")
            # Отправляем без HTML-разметки
            plain_text = text.replace('<b>', '').replace('</b>', '')
            await callback_query.message.answer(plain_text)
        else:
            # Разбиваем на части, если текст слишком длинный
            if len(text) > 4096:
                parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
                for i, part in enumerate(parts):
                    await callback_query.message.answer(part, parse_mode=ParseMode.HTML)
            else:
                await callback_query.message.answer(text, parse_mode=ParseMode.HTML)
        
        await callback_query.answer(f"Найдено {len(users)} пользователей")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре пользователей: {e}")
        
        # Пробуем отправить без HTML-разметки
        try:
            logger.info("Пробуем отправить список пользователей без HTML-разметки")
            plain_text = "👥 Авторизованные пользователи:\n\n"
            
            for i, user in enumerate(users[:20]):  # Ограничиваем 20 пользователями
                try:
                    user_id, username, fio, position, role = user
                    plain_text += f"👤 {fio or 'Не указано'}\n"
                    plain_text += f"🆔 ID: {user_id}\n"
                    plain_text += f"�� @{username or 'Нет'}\n"
                    plain_text += f"💼 {position or 'Не указано'}\n"
                    plain_text += f"👑 Роль: {role or 'user'}\n\n"
                except Exception as user_error:
                    logger.error(f"Ошибка обработки пользователя {user}: {user_error}")
                    continue
            
            if len(users) > 20:
                plain_text += f"... и еще {len(users) - 20} пользователей"
            
            await callback_query.message.answer(plain_text)
            await callback_query.answer(f"Отправлено {min(20, len(users))} пользователей (без форматирования)")
            
        except Exception as fallback_error:
            logger.error(f"Ошибка при отправке без HTML: {fallback_error}")
            await callback_query.answer("Произошла ошибка при загрузке пользователей.", show_alert=True)
            
@dp.callback_query(lambda c: c.data == "assign_role")
async def assign_role_callback(callback_query: types.CallbackQuery):
    """Обработчик кнопки назначения ролей - показывает список пользователей с пагинацией"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для назначения ролей.", show_alert=True)
            return
        
        # Получаем всех пользователей
        users = await get_authorized_users()
        
        if not users:
            await callback_query.message.answer("👥 Нет авторизованных пользователей.")
            await callback_query.answer()
            return
        
        # Показываем первую страницу
        await show_users_page(callback_query.message, users, 0)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при показе списка пользователей: {e}")
        await callback_query.answer("Произошла ошибка при загрузке пользователей.", show_alert=True)

async def show_users_page(message: types.Message, users: list, page: int, users_per_page: int = 7):
    """Показывает страницу пользователей с кнопками для назначения ролей и удаления"""
    try:
        total_pages = (len(users) + users_per_page - 1) // users_per_page
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, len(users))
        page_users = users[start_idx:end_idx]
        
        # Формируем текст сообщения
        text = f"👥 <b>Управление пользователями</b>\n\n"
        text += f"📄 Страница {page + 1} из {total_pages}\n"
        text += f"👤 Показано {len(page_users)} из {len(users)} пользователей\n\n"
        
        # Добавляем информацию о пользователях
        for i, user in enumerate(page_users):
            user_id, username, fio, position, role = user
            
            # Экранируем HTML-символы
            safe_fio = escape_html(fio) if fio else 'Не указано'
            safe_username = escape_html(username) if username else 'Нет'
            safe_position = escape_html(position) if position else 'Не указано'
            safe_role = escape_html(role) if role else 'user'
            
            text += f"<b>{start_idx + i + 1}.</b> 👤 <b>{safe_fio}</b>\n"
            text += f"🆔 ID: <code>{user_id}</code>\n"
            text += f"📱 @{safe_username}\n"
            text += f"💼 {safe_position}\n"
            text += f"👑 Роль: {safe_role}\n\n"
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardBuilder()
        
        # Кнопки для каждого пользователя
        for i, user in enumerate(page_users):
            user_id, username, fio, position, role = user
            user_num = start_idx + i + 1
            
            # Кнопка для выбора пользователя
            keyboard.add(InlineKeyboardButton(
                text=f"👤 {user_num}. {fio[:20]}{'...' if len(fio) > 20 else ''}",
                callback_data=f"select_user_{user_id}"
            ))
        
        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"users_page_{page - 1}"
            ))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"users_page_{page + 1}"
            ))
        
        if nav_row:
            keyboard.row(*nav_row)
        
        # Кнопка возврата в админ панель
        keyboard.add(InlineKeyboardButton(
            text="🔙 Назад в админ панель",
            callback_data="admin_panel"
        ))
        
        # Настройка расположения кнопок
        keyboard.adjust(1)  # По одной кнопке в ряду для пользователей
        
        await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при показе страницы пользователей: {e}")
        await message.answer("Произошла ошибка при отображении пользователей.")

@dp.callback_query(lambda c: c.data and c.data.startswith("users_page_"))
async def users_page_callback(callback_query: types.CallbackQuery):
    """Обработчик пагинации пользователей"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для просмотра пользователей.", show_alert=True)
            return
        
        # Парсим номер страницы
        page = int(callback_query.data.split("_")[2])
        
        # Получаем всех пользователей
        users = await get_authorized_users()
        
        if not users:
            await callback_query.message.answer("👥 Нет авторизованных пользователей.")
            await callback_query.answer()
            return
        
        # Показываем нужную страницу
        await show_users_page(callback_query.message, users, page)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при переключении страницы пользователей: {e}")
        await callback_query.answer("Произошла ошибка при переключении страницы.", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("select_user_"))
async def select_user_callback(callback_query: types.CallbackQuery):
    """Обработчик выбора пользователя для управления"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для управления пользователями.", show_alert=True)
            return
        
        # Парсим ID пользователя
        user_id = int(callback_query.data.split("_")[2])
        
        # Получаем информацию о пользователе
        user_info = await get_user_info(user_id)
        
        if not user_info:
            await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        user_id, username, fio, position, role = user_info
        
        # Экранируем HTML-символы
        safe_fio = escape_html(fio) if fio else 'Не указано'
        safe_username = escape_html(username) if username else 'Нет'
        safe_position = escape_html(position) if position else 'Не указано'
        safe_role = escape_html(role) if role else 'user'
        
        # Формируем текст
        text = f"👤 <b>Управление пользователем</b>\n\n"
        text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        text += f"👤 <b>ФИО:</b> {safe_fio}\n"
        text += f"📱 <b>Username:</b> @{safe_username}\n"
        text += f"💼 <b>Должность:</b> {safe_position}\n"
        text += f"👑 <b>Текущая роль:</b> {safe_role}\n\n"
        text += "Выберите действие:"
        
        # Создаем клавиатуру с действиями
        keyboard = InlineKeyboardBuilder()
        
        # Кнопки назначения ролей
        roles = [
            ("👑 Администратор", "admin"),
            ("🛡️ Модератор", "moderator"),
            ("📢 Маркетолог", "marketer"),
            ("👤 Пользователь", "user")
        ]
        
        for role_name, role_value in roles:
            if role_value != role:  # Не показываем текущую роль
                keyboard.add(InlineKeyboardButton(
                    text=f"Назначить {role_name}",
                    callback_data=f"assign_role_{user_id}_{role_value}"
                ))
        
        # Кнопка удаления пользователя
        keyboard.add(InlineKeyboardButton(
            text="❌ Удалить пользователя",
            callback_data=f"confirm_delete_{user_id}"
        ))
        
        # Кнопка возврата
        keyboard.add(InlineKeyboardButton(
            text="🔙 Назад к списку",
            callback_data="assign_role"
        ))
        
        # Настройка расположения кнопок
        keyboard.adjust(1)  # По одной кнопке в ряду
        
        await callback_query.message.answer(text, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе пользователя: {e}")
        await callback_query.answer("Произошла ошибка при выборе пользователя.", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("confirm_delete_"))
async def confirm_delete_user_callback(callback_query: types.CallbackQuery):
    """Обработчик подтверждения удаления пользователя"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для удаления пользователей.", show_alert=True)
            return
        
        # Парсим ID пользователя
        user_id = int(callback_query.data.split("_")[2])
        
        # Получаем информацию о пользователе
        user_info = await get_user_info(user_id)
        
        if not user_info:
            await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        user_id, username, fio, position, role = user_info
        
        # Экранируем HTML-символы
        safe_fio = escape_html(fio) if fio else 'Не указано'
        
        # Формируем текст подтверждения
        text = f"⚠️ <b>Подтверждение удаления</b>\n\n"
        text += f"Вы действительно хотите удалить пользователя:\n\n"
        text += f"👤 <b>ФИО:</b> {safe_fio}\n"
        text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        text += f"👑 <b>Роль:</b> {role}\n\n"
        text += "⚠️ <b>Внимание:</b> Это действие нельзя отменить!"
        
        # Создаем клавиатуру подтверждения
        keyboard = InlineKeyboardBuilder()
        
        keyboard.add(InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"delete_user_{user_id}"
        ))
        keyboard.add(InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"select_user_{user_id}"
        ))
        
        keyboard.adjust(2)
        
        await callback_query.message.answer(text, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении удаления: {e}")
        await callback_query.answer("Произошла ошибка при подтверждении удаления.", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("delete_user_"))
async def delete_user_callback(callback_query: types.CallbackQuery):
    """Обработчик удаления пользователя"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для удаления пользователей.", show_alert=True)
            return
        
        # Парсим ID пользователя
        user_id = int(callback_query.data.split("_")[2])
        
        # Получаем информацию о пользователе перед удалением
        user_info = await get_user_info(user_id)
        
        if not user_info:
            await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        user_id, username, fio, position, role = user_info
        
        # Удаляем пользователя
        success = await remove_user(user_id)
        
        if success:
            # Логируем действие
            await log_admin_action(callback_query.from_user.id, f"delete_user_{user_id}")
            
            # Отправляем подтверждение
            safe_fio = escape_html(fio) if fio else 'Не указано'
            await callback_query.message.answer(
                f"✅ Пользователь <b>{safe_fio}</b> (ID: {user_id}) успешно удален.",
                parse_mode=ParseMode.HTML
            )
        else:
            await callback_query.message.answer("❌ Произошла ошибка при удалении пользователя.")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        await callback_query.answer("Произошла ошибка при удалении пользователя.", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("assign_role_"))
async def assign_role_callback_handler(callback_query: types.CallbackQuery):
    """Обработчик назначения роли через кнопки"""
    try:
        # Проверяем права администратора
        if callback_query.from_user.id != ADMIN_ID:
            await callback_query.answer("❌ У вас нет прав для назначения ролей.", show_alert=True)
            return
        
        # Парсим callback_data: assign_role_{user_id}_{role}
        parts = callback_query.data.split("_")
        if len(parts) >= 4:
            user_id = int(parts[2])
            role = parts[3]
            
            # Получаем информацию о пользователе
            user_info = await get_user_info(user_id)
            
            if not user_info:
                await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
                return
            
            user_id, username, fio, position, old_role = user_info
            
            # Назначаем роль
            success = await assign_user_role(user_id, role, callback_query.from_user.id)
            
            if success:
                # Логируем действие
                await log_admin_action(callback_query.from_user.id, f"assign_role_{user_id}_{old_role}_{role}")
                
                # Отправляем подтверждение
                role_names = {
                    'admin': '👑 Администратор',
                    'moderator': '🛡️ Модератор', 
                    'marketer': '📢 Маркетолог',
                    'user': '👤 Пользователь'
                }
                
                role_name = role_names.get(role, role)
                safe_fio = escape_html(fio) if fio else 'Не указано'
                
                await callback_query.message.answer(
                    f"✅ Роль <b>{role_name}</b> назначена пользователю <b>{safe_fio}</b> (ID: {user_id})",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.message.answer("❌ Произошла ошибка при назначении роли.")
        else:
            await callback_query.message.answer("❌ Неверный формат данных для назначения роли.")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при назначении роли: {e}")
        await callback_query.answer("Произошла ошибка при назначении роли.", show_alert=True)

@dp.callback_query(lambda c: c.data == "send_notification")
async def send_notification_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Введите текст уведомления для всех пользователей:")
    await state.set_state(Notify.waiting_for_notification)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "sync_data")
async def sync_data_callback(callback_query: types.CallbackQuery):
    await callback_query.message.answer("🔄 Синхронизация данных...")
    try:
        logger.info(f"Запуск синхронизации от {callback_query.from_user.id}")
        
        # Проверяем и обновляем базу данных
        sync_results = []
        
        # Проверяем таблицу авторизованных пользователей
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM authorized_users")
                user_count = (await cursor.fetchone())[0]
                sync_results.append(f"✅ Пользователи: {user_count} записей")
        except Exception as e:
            sync_results.append(f"❌ Пользователи: ошибка - {e}")
        
        # Проверяем таблицу заявок
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM auth_requests")
                request_count = (await cursor.fetchone())[0]
                sync_results.append(f"✅ Заявки: {request_count} записей")
        except Exception as e:
            sync_results.append(f"❌ Заявки: ошибка - {e}")

        # Проверяем таблицу новостей
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM news_proposals")
                news_count = (await cursor.fetchone())[0]
                sync_results.append(f"✅ Новости: {news_count} записей")
        except Exception as e:
            sync_results.append(f"❌ Новости: ошибка - {e}")
        
        # Проверяем таблицу подписчиков канала
        try:
            async with aiosqlite.connect(DB_PATH) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM channel_subscribers")
                channel_count = (await cursor.fetchone())[0]
                sync_results.append(f"✅ Подписчики канала: {channel_count} записей")
        except Exception as e:
            sync_results.append(f"❌ Подписчики канала: ошибка - {e}")
        
        # Формируем отчет
        report = "🔄 <b>Отчет о синхронизации базы данных</b>\n\n"
        report += "\n".join(sync_results)
        report += f"\n\n📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        await callback_query.message.answer(report, parse_mode=ParseMode.HTML)
        await callback_query.answer("Синхронизация завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        await callback_query.message.answer(f"❌ Ошибка синхронизации: {e}")
        await callback_query.answer("Ошибка синхронизации", show_alert=True)

@dp.callback_query(lambda c: c.data == "sync_channel")
async def sync_channel_callback(callback_query: types.CallbackQuery):
    """Обработчик синхронизации канала с Excel файлом"""
    # Проверяем права администратора
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
        return
    
    await callback_query.message.answer("🔄 Запуск синхронизации канала с Excel файлом...")
    await sync_channel_with_excel()
    await callback_query.message.answer("✅ Синхронизация канала завершена!")
    await callback_query.answer()

# Обработчики модератора
@dp.callback_query(lambda c: c.data == "publish_news")
async def publish_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📢 Введите текст новости для публикации:")
    await state.set_state(Moderator.waiting_for_news)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "schedule_month")
async def schedule_month_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📅 Введите график в формате:\nФИО: ДД-ММ-ГГГГ\nФИО: ДД-ММ-ГГГГ")
    await state.set_state(ScheduleMonth.waiting_for_schedule)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "news_proposals")
async def news_proposals_callback(callback_query: types.CallbackQuery):
    """Обработчик для просмотра предложений новостей (модератор)"""
    await view_news_proposals_callback(callback_query)

@dp.callback_query(lambda c: c.data == "statistics")
async def statistics_callback(callback_query: types.CallbackQuery):
    try:
        logger.info(f"Запрос статистики от {callback_query.from_user.id}")
        
        # Получаем реальную статистику
        async with aiosqlite.connect(DB_PATH) as conn:
            # Количество пользователей
            try:
                async with conn.execute("SELECT COUNT(*) FROM authorized_users") as cursor:
                    users_count = (await cursor.fetchone())[0]
            except Exception:
                users_count = 0
            
            # Количество предложений новостей
            try:
                async with conn.execute("SELECT COUNT(*) FROM news_proposals") as cursor:
                    proposals_count = (await cursor.fetchone())[0]
            except Exception:
                proposals_count = 0
            
            # Количество записей в графике кофе
            try:
                async with conn.execute("SELECT COUNT(*) FROM coffee_schedule") as cursor:
                    coffee_count = (await cursor.fetchone())[0]
            except Exception:
                coffee_count = 0
            
            # Количество заявок на авторизацию
            try:
                async with conn.execute("SELECT COUNT(*) FROM auth_requests WHERE status = 'pending'") as cursor:
                    pending_requests = (await cursor.fetchone())[0]
            except Exception:
                pending_requests = 0
        
        stats_text = "📊 <b>Статистика системы:</b>\n\n"
        stats_text += f"👥 <b>Пользователей:</b> {users_count}\n"
        stats_text += f"�� <b>Предложений новостей:</b> {proposals_count}\n"
        stats_text += f"�� <b>Записей в графике кофе:</b> {coffee_count}\n"
        stats_text += f"⏳ <b>Ожидающих заявок:</b> {pending_requests}\n"
        
        await callback_query.message.answer(stats_text, parse_mode=ParseMode.HTML)
        await callback_query.answer()
        logger.info(f"Статистика отправлена пользователю {callback_query.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await callback_query.answer("Произошла ошибка при получении статистики.", show_alert=True)

# Обработчики маркетолога
@dp.callback_query(lambda c: c.data == "review_news_proposals")
async def review_news_proposals_callback(callback_query: types.CallbackQuery):
    await view_news_proposals_callback(callback_query)

@dp.callback_query(lambda c: c.data == "publication_stats")
async def publication_stats_callback(callback_query: types.CallbackQuery):
    try:
        # Получаем статистику публикаций
        async with aiosqlite.connect(DB_PATH) as conn:
            # Количество одобренных новостей
            async with conn.execute("SELECT COUNT(*) FROM news_proposals WHERE status = 'approved'") as cursor:
                approved_count = (await cursor.fetchone())[0]
            
            # Количество отклоненных новостей
            async with conn.execute("SELECT COUNT(*) FROM news_proposals WHERE status = 'rejected'") as cursor:
                rejected_count = (await cursor.fetchone())[0]
            
            # Количество ожидающих новостей
            async with conn.execute("SELECT COUNT(*) FROM news_proposals WHERE status = 'pending'") as cursor:
                pending_count = (await cursor.fetchone())[0]
            
            # Количество прокомментированных новостей
            async with conn.execute("SELECT COUNT(*) FROM news_proposals WHERE status = 'commented'") as cursor:
                commented_count = (await cursor.fetchone())[0]
        
        stats_text = "📊 <b>Статистика публикаций:</b>\n\n"
        stats_text += f"✅ <b>Одобрено:</b> {approved_count}\n"
        stats_text += f"❌ <b>Отклонено:</b> {rejected_count}\n"
        stats_text += f"⏳ <b>Ожидает:</b> {pending_count}\n"
        stats_text += f"💬 <b>Прокомментировано:</b> {commented_count}\n"
        
        await callback_query.message.answer(stats_text, parse_mode=ParseMode.HTML)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики публикаций: {e}")
        await callback_query.answer("Произошла ошибка при получении статистики.", show_alert=True)

@dp.callback_query(lambda c: c.data == "create_news")
async def create_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📝 Введите текст новости для создания:")
    await state.set_state(Moderator.waiting_for_news)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "content_scheduler")
async def content_scheduler_callback(callback_query: types.CallbackQuery):
    await callback_query.message.answer("📅 Планировщик контента\n\nФункция в разработке.")
    await callback_query.answer()

# Основная функция
async def check_and_fix_database():
    """Проверяет и исправляет структуру базы данных, добавляя недостающие таблицы и колонки"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем и исправляем таблицу coffee_schedule
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coffee_schedule'")
            table_exists = await cursor.fetchone()
            
            if table_exists:
                logger.info("📋 Таблица coffee_schedule существует. Проверяем структуру...")
                cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                logger.info(f"📊 Текущие колонки coffee_schedule: {column_names}")
                
                # Проверяем наличие нужных колонок
                required_columns = ['id', 'fio', 'date', 'user_id', 'created_by', 'created_at', 'notified_at', 'reminder_sent_at']
                missing_columns = [col for col in required_columns if col not in column_names]
                
                if missing_columns:
                    logger.info(f"🔧 Отсутствующие колонки в coffee_schedule: {missing_columns}")
                    logger.info("🔧 Добавляем недостающие колонки...")
                    
                    for col in missing_columns:
                        if col == 'id':
                            logger.info("  ⚠️ Пропускаем добавление id через ALTER TABLE (невозможно добавить PRIMARY KEY)")
                            continue  # id уже есть как PRIMARY KEY, нельзя добавить через ALTER TABLE
                        elif col == 'user_id':
                            logger.info("  ➕ Добавляем колонку user_id...")
                            await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN user_id INTEGER')
                        elif col == 'created_by':
                            logger.info("  ➕ Добавляем колонку created_by...")
                            await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN created_by INTEGER')
                        elif col == 'created_at':
                            logger.info("  ➕ Добавляем колонку created_at...")
                            await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN created_at DATETIME')
                        elif col == 'notified_at':
                            logger.info("  ➕ Добавляем колонку notified_at...")
                            await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN notified_at DATETIME')
                        elif col == 'reminder_sent_at':
                            logger.info("  ➕ Добавляем колонку reminder_sent_at...")
                            await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN reminder_sent_at DATETIME')
                    
                    logger.info("✅ Колонки в coffee_schedule добавлены успешно!")
                else:
                    logger.info("✅ Все необходимые колонки в coffee_schedule уже существуют.")
            else:
                logger.info("📋 Таблица coffee_schedule не существует. Создаем новую...")
                await conn.execute('''
                    CREATE TABLE coffee_schedule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fio TEXT NOT NULL,
                        date TEXT NOT NULL,
                        user_id INTEGER,
                        created_by INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        notified_at DATETIME,
                        reminder_sent_at DATETIME
                    )
                ''')
                logger.info("✅ Таблица coffee_schedule создана успешно!")
            
            # Проверяем и исправляем таблицу authorized_users (добавляем колонку role если её нет)
            try:
                cursor = await conn.execute("PRAGMA table_info(authorized_users)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'role' not in column_names:
                    logger.info("🔧 Добавляем колонку role в authorized_users...")
                    logger.info("  ➕ Добавляем колонку role...")
                    await conn.execute('ALTER TABLE authorized_users ADD COLUMN role TEXT DEFAULT "user"')
                    logger.info("✅ Колонка role добавлена в authorized_users!")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить таблицу authorized_users: {e}")
            
            # Проверяем и исправляем таблицу channel_subscribers
            try:
                cursor = await conn.execute("PRAGMA table_info(channel_subscribers)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'username' not in column_names:
                    logger.info("🔧 Добавляем колонку username в channel_subscribers...")
                    await conn.execute('ALTER TABLE channel_subscribers ADD COLUMN username TEXT')
                    logger.info("✅ Колонка username добавлена в channel_subscribers!")
                
                if 'subscribed_at' not in column_names:
                    logger.info("🔧 Добавляем колонку subscribed_at в channel_subscribers...")
                    await conn.execute('ALTER TABLE channel_subscribers ADD COLUMN subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP')
                    logger.info("✅ Колонка subscribed_at добавлена в channel_subscribers!")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить таблицу channel_subscribers: {e}")
            
            # Проверяем и исправляем таблицу auth_requests
            try:
                cursor = await conn.execute("PRAGMA table_info(auth_requests)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'timestamp' not in column_names:
                    logger.info("🔧 Добавляем колонку timestamp в auth_requests...")
                    logger.info("  ➕ Добавляем колонку timestamp...")
                    await conn.execute('ALTER TABLE auth_requests ADD COLUMN timestamp TEXT')
                    logger.info("✅ Колонка timestamp добавлена в auth_requests!")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить таблицу auth_requests: {e}")
            
            # Проверяем и исправляем таблицу news_proposals
            try:
                cursor = await conn.execute("PRAGMA table_info(news_proposals)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                required_news_columns = ['id', 'user_id', 'username', 'fio', 'news_text', 'photos', 'status', 'marketer_id', 'marketer_comment', 'created_at', 'processed_at']
                missing_news_columns = [col for col in required_news_columns if col not in column_names]
                
                if missing_news_columns:
                    logger.info(f"🔧 Отсутствующие колонки в news_proposals: {missing_news_columns}")
                    logger.info("🔧 Добавляем недостающие колонки...")
                    for col in missing_news_columns:
                        if col == 'id':
                            logger.info("  ⚠️ Пропускаем добавление id через ALTER TABLE (невозможно добавить PRIMARY KEY)")
                            continue
                        elif col in ['user_id', 'marketer_id']:
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE news_proposals ADD COLUMN {col} INTEGER')
                        elif col in ['created_at', 'processed_at']:
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE news_proposals ADD COLUMN {col} DATETIME')
                        else:
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE news_proposals ADD COLUMN {col} TEXT')
                    logger.info("✅ Колонки в news_proposals добавлены успешно!")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить таблицу news_proposals: {e}")
            
            # Проверяем и исправляем таблицу admin_logs
            try:
                cursor = await conn.execute("PRAGMA table_info(admin_logs)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                required_admin_columns = ['id', 'admin_id', 'action', 'target_user_id', 'timestamp']
                missing_admin_columns = [col for col in required_admin_columns if col not in column_names]
                
                if missing_admin_columns:
                    logger.info(f"🔧 Отсутствующие колонки в admin_logs: {missing_admin_columns}")
                    logger.info("🔧 Добавляем недостающие колонки...")
                    for col in missing_admin_columns:
                        if col == 'id':
                            logger.info("  ⚠️ Пропускаем добавление id через ALTER TABLE (невозможно добавить PRIMARY KEY)")
                            continue
                        elif col in ['admin_id', 'target_user_id']:
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE admin_logs ADD COLUMN {col} INTEGER')
                        elif col == 'timestamp':
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE admin_logs ADD COLUMN {col} DATETIME')
                        else:
                            logger.info(f"  ➕ Добавляем колонку {col}...")
                            await conn.execute(f'ALTER TABLE admin_logs ADD COLUMN {col} TEXT')
                    logger.info("✅ Колонки в admin_logs добавлены успешно!")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить таблицу admin_logs: {e}")
            
            # Проверяем и исправляем основные таблицы, если они не существуют
            try:
                # authorized_users
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='authorized_users'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу authorized_users...")
                    await conn.execute('''
                        CREATE TABLE authorized_users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            fio TEXT,
                            position TEXT,
                            role TEXT DEFAULT 'user'
                        )
                    ''')
                    logger.info("✅ Таблица authorized_users создана!")
                
                # auth_requests
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_requests'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу auth_requests...")
                    await conn.execute('''
                        CREATE TABLE auth_requests (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            fio TEXT,
                            position TEXT,
                            timestamp TEXT
                        )
                    ''')
                    logger.info("✅ Таблица auth_requests создана!")
                
                # news_proposals
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news_proposals'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу news_proposals...")
                    await conn.execute('''
                        CREATE TABLE news_proposals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            username TEXT,
                            fio TEXT,
                            news_text TEXT,
                            photos TEXT,
                            status TEXT DEFAULT 'pending',
                            marketer_id INTEGER,
                            marketer_comment TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            processed_at DATETIME
                        )
                    ''')
                    logger.info("✅ Таблица news_proposals создана!")
                
                # admin_logs
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_logs'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу admin_logs...")
                    await conn.execute('''
                        CREATE TABLE admin_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            admin_id INTEGER,
                            action TEXT,
                            target_user_id INTEGER,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    logger.info("✅ Таблица admin_logs создана!")
                
                # channel_subscribers
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_subscribers'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу channel_subscribers...")
                    await conn.execute('''
                        CREATE TABLE channel_subscribers (
                            user_id INTEGER PRIMARY KEY,
                            fio TEXT,
                            username TEXT,
                            subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    logger.info("✅ Таблица channel_subscribers создана!")
                
                # notified_channel_subscribers
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notified_channel_subscribers'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу notified_channel_subscribers...")
                    await conn.execute('CREATE TABLE notified_channel_subscribers (user_id INTEGER PRIMARY KEY)')
                    logger.info("✅ Таблица notified_channel_subscribers создана!")
                
                # notified_bot_users
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notified_bot_users'")
                if not await cursor.fetchone():
                    logger.info("📋 Создаем таблицу notified_bot_users...")
                    await conn.execute('CREATE TABLE notified_bot_users (user_id INTEGER PRIMARY KEY)')
                    logger.info("✅ Таблица notified_bot_users создана!")
                    
            except Exception as e:
                logger.warning(f"⚠️ Не удалось проверить основные таблицы: {e}")
            
            await conn.commit()
            logger.info("✅ Проверка и исправление базы данных завершены успешно!")
            
            # Очищаем некорректные записи графика кофе
            logger.info("🧹 Очистка некорректных записей графика кофе...")
            await clean_invalid_coffee_entries()
            logger.info("✅ Очистка некорректных записей графика кофе завершена")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке и исправлении базы данных: {e}")

async def main():
    logger.info("🚀 Запуск бота...")
    logger.info("🔧 Проверка и исправление базы данных...")
    # Проверяем и исправляем базу данных
    await check_and_fix_database()
    
    # Инициализация базы данных
    logger.info("��️ Инициализация базы данных...")
    await init_db()
    await init_channel_subscribers_table()
    await init_notified_channel_subscribers_table()
    await init_notified_bot_users_table()
    await ensure_auth_requests_timestamp_column()
    logger.info("✅ Инициализация базы данных завершена")
    
    # Назначаем роли администраторам
    logger.info("👑 Назначение ролей администраторам...")
    await assign_roles()
    logger.info("✅ Роли администраторам назначены")
    
    # Автоматическая миграция ролей из переменных окружения
    logger.info("🔄 Проверка необходимости миграции ролей...")
    await migrate_roles_from_env()
    
    # Опциональная очистка старых переменных из .env файла
    # Раскомментируйте следующую строку, если хотите автоматически удалять старые переменные
    # await cleanup_env_roles()
    
    # Создаем тестового пользователя, если база пустая
    try:
        logger.info("👥 Проверка и создание тестовых пользователей...")
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute("SELECT COUNT(*) FROM authorized_users") as cursor:
                users_count = (await cursor.fetchone())[0]
            
            if users_count == 0:
                logger.info("База пользователей пуста. Создаем тестового администратора...")
                # Создаем только тестового администратора
                await conn.execute('''
                    INSERT INTO authorized_users (user_id, username, fio, position, role) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (ADMIN_ID, 'admin', 'Администратор Системы', 'Главный администратор', 'admin'))
                
                await conn.commit()
                logger.info("✅ Создан тестовый администратор")
            else:
                logger.info(f"✅ В базе уже есть {users_count} пользователей")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при создании тестовых пользователей: {e}")
    
    # Запускаем веб-интерфейс в отдельном потоке
    logger.info("🌐 Запуск Flask веб-интерфейса...")
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask веб-интерфейс запущен на http://localhost:5000")
    
    # Запускаем планировщик уведомлений о кофемашине
    logger.info("☕ Запуск планировщика уведомлений о кофемашине...")
    coffee_notification_task = asyncio.create_task(schedule_coffee_notifications())
    logger.info("✅ Планировщик уведомлений о кофемашине запущен (проверка в 11:00, отправка в 16:00)")
    
    # Запускаем периодическую синхронизацию канала
    logger.info("📢 Запуск периодической синхронизации канала...")
    channel_sync_task = asyncio.create_task(periodic_channel_sync())
    logger.info("✅ Периодическая синхронизация канала запущена")
    
    # Запускаем синхронизацию канала при старте
    logger.info("🔄 Запуск синхронизации канала при старте...")
    await sync_channel_with_excel()
    logger.info("✅ Синхронизация канала при старте завершена")
    
    logger.info("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

async def clear_old_keyboards():
    """Очищает старые клавиатуры у всех пользователей"""
    try:
        logger.info("🧹 Начинаем очистку старых клавиатур...")
        user_ids = await get_all_authorized_user_ids()
        logger.info(f"Найдено {len(user_ids)} пользователей для очистки клавиатур")
        
        cleared_count = 0
        for user_id in user_ids:
            try:
                # Отправляем новое главное меню, которое заменит старые клавиатуры
                await send_main_menu(
                    types.Message(
                        message_id=0,
                        date=datetime.now(),
                        chat=types.Chat(id=user_id, type="private"),
                        from_user=types.User(id=user_id, is_bot=False, first_name="User")
                    ),
                    user_id=user_id
                )
                cleared_count += 1
                logger.info(f"Очищена клавиатура для пользователя {user_id}")
            except Exception as e:
                logger.warning(f"Не удалось очистить клавиатуру для пользователя {user_id}: {e}")
        
        logger.info(f"✅ Очистка завершена. Обработано {cleared_count} пользователей")
        return cleared_count
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке старых клавиатур: {e}")
        return 0

@dp.callback_query(lambda c: c.data and c.data.startswith("edit_news_"))
async def edit_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    proposal_id = int(callback_query.data.split("_")[-1])
    await state.update_data(editing_proposal_id=proposal_id)
    await callback_query.message.answer("✏️ Введите новый текст новости:")
    await state.set_state(EditNewsProposal.waiting_for_text)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("comment_news_"))
async def comment_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    proposal_id = int(callback_query.data.split("_")[-1])
    await state.update_data(commenting_proposal_id=proposal_id)
    await callback_query.message.answer("💬 Введите комментарий к предложению:")
    await state.set_state(CommentNews.waiting_for_comment)
    await callback_query.answer()

# Обработчики состояний редактирования и комментирования
@dp.message(EditNewsProposal.waiting_for_text)
async def process_edit_news_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    proposal_id = data.get('editing_proposal_id')
    
    try:
        await update_news_proposal_content(proposal_id, message.text, None)
        await message.answer(f"✅ Текст предложения #{proposal_id} обновлен!")
    except Exception as e:
        logger.error(f"Ошибка при редактировании новости: {e}")
        await message.answer("❌ Произошла ошибка при редактировании новости.")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

@dp.message(CommentNews.waiting_for_comment)
async def process_comment_news(message: types.Message, state: FSMContext):
    data = await state.get_data()
    proposal_id = data.get('commenting_proposal_id')
    
    try:
        await update_news_proposal_status(proposal_id, 'commented', message.from_user.id, message.text)
        await message.answer(f"✅ Комментарий к предложению #{proposal_id} добавлен!")
    except Exception as e:
        logger.error(f"Ошибка при добавлении комментария: {e}")
        await message.answer("❌ Произошла ошибка при добавлении комментария.")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

# Обработчики состояний предложения новостей
@dp.message(NewsProposal.waiting_for_text)
async def process_news_text(message: types.Message, state: FSMContext):
    logger.debug(f"NEWS_TEXT: user_id={message.from_user.id}, text_length={len(message.text)}")
    await state.update_data(news_text=message.text)
    await message.answer(
        "📸 Теперь отправьте фотографии для новости (можно несколько).\n"
        "Когда закончите, нажмите кнопку 'Отправить предложение' или напишите 'Готово'."
    )
    await state.set_state(NewsProposal.waiting_for_photos)

@dp.message(NewsProposal.waiting_for_photos, F.photo)
async def process_news_photo(message: types.Message, state: FSMContext):
    logger.debug(f"NEWS_PHOTO: user_id={message.from_user.id}, photo_id={message.photo[-1].file_id}")
    data = await state.get_data()
    photos = data.get('photos', [])
    photo = message.photo[-1]
    photos.append(photo.file_id)
    await state.update_data(photos=photos)
    
    # Удаляем клавиатуру у предыдущего сообщения, если оно есть
    last_keyboard_msg_id = data.get('last_keyboard_msg_id')
    if last_keyboard_msg_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=last_keyboard_msg_id,
                reply_markup=None
            )
        except Exception:
            pass
    
    sent = await message.answer(
        f"📸 Фотография добавлена! Всего фотографий: {len(photos)}",
        reply_markup=BeautifulInlineKeyboards.create_news_photos_keyboard()
    )
    await state.update_data(last_keyboard_msg_id=sent.message_id)

@dp.callback_query(lambda c: c.data == "news_photos_done")
async def news_photos_done_callback(callback_query: types.CallbackQuery, state: FSMContext):
    logger.debug(f"CALLBACK: news_photos_done from user {callback_query.from_user.id}")
    current_state = await state.get_state()
    logger.debug(f"CALLBACK: news_photos_done current_state={current_state}, expected={NewsProposal.waiting_for_photos.state}")
    
    if current_state != NewsProposal.waiting_for_photos.state:
        logger.debug(f"CALLBACK: news_photos_done wrong state for user {callback_query.from_user.id}")
        await callback_query.answer("Вы уже завершили предложение новости.", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    
    await finish_news_proposal(callback_query.message, state, from_callback=True, real_user_id=callback_query.from_user.id)
    await callback_query.answer()
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

@dp.message(NewsProposal.waiting_for_photos, F.text)
async def finish_news_proposal(message: types.Message, state: FSMContext, from_callback=False, real_user_id=None):
    if real_user_id is None:
        real_user_id = message.from_user.id
    
    logger.debug(f"FINISH_NEWS: user_id={real_user_id}, from_callback={from_callback}")
    
    data = await state.get_data()
    news_text = data.get('news_text', '')
    photos = data.get('photos', [])
    
    if not news_text.strip():
        await message.answer("❌ Текст новости не может быть пустым.")
        await state.clear()
        await send_main_menu(message, user_id=real_user_id)
        return
    
    try:
        # Получаем информацию о пользователе
        user_info = await get_user_info(real_user_id)
        if not user_info:
            await message.answer("❌ Ошибка: пользователь не найден в базе данных.")
            await state.clear()
            await send_main_menu(message, user_id=real_user_id)
            return
        
        fio = user_info[2]  # Предполагаем, что FIO находится в третьем поле
        
        # Сохраняем предложение в базу данных
        photos_json = json.dumps(photos) if photos else None
        proposal_id = await add_news_proposal(real_user_id, message.from_user.username, fio, news_text, photos_json)
        
        logger.info(f"NEWS_PROPOSAL: saved proposal_id={proposal_id} from user_id={real_user_id}")
        
        # Уведомляем маркетолога
        marketer_message = (
            f"📋 <b>Новое предложение новости #{proposal_id}</b>\n\n"
            f"�� <b>Автор:</b> {fio}\n"
            f"🆔 <b>ID:</b> {real_user_id}\n"
            f"�� <b>Username:</b> @{message.from_user.username or 'Нет'}\n"
            f"�� <b>Фотографий:</b> {len(photos)}\n\n"
            f"📄 <b>Текст новости:</b>\n{news_text[:300]}{'...' if len(news_text) > 300 else ''}"
        )
        
        # Создаем клавиатуру для маркетолога
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="✅ Одобрить и опубликовать", callback_data=f"approve_news_{proposal_id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_news_{proposal_id}"))
        keyboard.add(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_news_{proposal_id}"))
        keyboard.add(InlineKeyboardButton(text="💬 Добавить комментарий", callback_data=f"comment_news_{proposal_id}"))
        keyboard.adjust(2, 2)
        
        # Отправляем уведомление маркетологу
        await bot.send_message(MARKETER_ID, marketer_message, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
        
        # Отправляем подтверждение пользователю
        await message.answer(
            f"✅ Ваше предложение новости отправлено маркетологу!\n\n"
            f"📋 <b>Номер предложения:</b> #{proposal_id}\n"
            f"📄 <b>Текст:</b> {news_text[:100]}{'...' if len(news_text) > 100 else ''}\n"
            f"�� <b>Фотографий:</b> {len(photos)}\n\n"
            f"Ожидайте решения маркетолога.",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"NEWS_PROPOSAL: success for user_id={real_user_id}, proposal_id={proposal_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении предложения новости: {e}")
        await message.answer("❌ Произошла ошибка при отправке предложения. Попробуйте позже.")
    
    await state.clear()
    await send_main_menu(message, user_id=real_user_id)

# Вспомогательные функции поиска
def search_by_fio(df, fio):
    """Поиск по ФИО с учетом Е/Ё и регистра"""
    if fio is None or fio.strip() == '':
        return df
    
    search_term = normalize_fio(fio)
    
    # Создаем временную колонку с нормализованными ФИО для поиска
    df_temp = df.copy()
    df_temp['ФИО_normalized'] = df_temp['ФИО'].astype(str).apply(normalize_fio)
    
    # Ищем совпадения
    results = df_temp[df_temp['ФИО_normalized'].str.contains(search_term, case=False, na=False)]
    
    # Удаляем временную колонку
    results = results.drop('ФИО_normalized', axis=1)
    
    return results

def search_by_position(df, position):
    """Поиск по должности с учетом Е/Ё и регистра"""
    if position is None or position.strip() == '':
        return df
    
    search_term = normalize_fio(position)  # Используем ту же функцию нормализации
    
    # Создаем временную колонку с нормализованными должностями для поиска
    df_temp = df.copy()
    df_temp['Должность_normalized'] = df_temp['Должность'].astype(str).apply(normalize_fio)
    
    # Ищем совпадения
    results = df_temp[df_temp['Должность_normalized'].str.contains(search_term, case=False, na=False)]
    
    # Удаляем временную колонку
    results = results.drop('Должность_normalized', axis=1)
    
    return results

def search_by_department(df, department):
    """Поиск по отделу с учетом Е/Ё и регистра"""
    if department is None or department.strip() == '':
        return df
    
    search_term = normalize_fio(department)  # Используем ту же функцию нормализации
    
    # Создаем временную колонку с нормализованными отделами для поиска
    df_temp = df.copy()
    df_temp['Отдел_normalized'] = df_temp['Отдел'].astype(str).apply(normalize_fio)
    
    # Ищем совпадения
    results = df_temp[df_temp['Отдел_normalized'].str.contains(search_term, case=False, na=False)]
    
    # Удаляем временную колонку
    results = results.drop('Отдел_normalized', axis=1)
    
    return results

# Обработчики состояний
@dp.message(AssignRole.waiting_for_user_id)
async def process_assign_role_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(target_user_id=user_id)
        await message.answer("Выберите роль:", reply_markup=BeautifulInlineKeyboards.create_role_selection_keyboard(user_id))
        await state.set_state(AssignRole.waiting_for_role)
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")

@dp.message(AssignRole.waiting_for_role)
async def process_assign_role_role(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    role = message.text.strip().lower()
    
    if role in ['admin', 'moderator', 'marketer', 'user']:
        try:
            # Используем новую функцию для назначения роли
            success = await assign_user_role(target_user_id, role, message.from_user.id)
            
            if success:
                await message.answer(f"✅ Роль '{role}' назначена пользователю {target_user_id}")
            else:
                await message.answer("❌ Произошла ошибка при назначении роли.")
        except Exception as e:
            logger.error(f"Ошибка при назначении роли: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}")
    else:
        await message.answer("❌ Неверная роль. Доступные роли: admin, moderator, marketer, user")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

@dp.message(RemoveUser.waiting_for_user_id)
async def process_remove_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await remove_user(user_id)
        await message.answer(f"✅ Пользователь {user_id} удален из системы.")
        await log_admin_action(message.from_user.id, f"Удалил пользователя {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        await message.answer("❌ Произошла ошибка при удалении пользователя.")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

@dp.message(Notify.waiting_for_notification)
async def process_notification_text(message: types.Message, state: FSMContext):
    try:
        users = await get_authorized_users()
        sent_count = 0
        for user in users:
            user_id = user[0]
            try:
                await bot.send_message(user_id, f"🔔 <b>Уведомление от администратора:</b>\n\n{message.text}", parse_mode=ParseMode.HTML)
                sent_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        await message.answer(f"✅ Уведомление отправлено {sent_count} пользователям из {len(users)}")
        await log_admin_action(message.from_user.id, f"Отправил уведомление {len(users)} пользователям")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")
        await message.answer("❌ Произошла ошибка при отправке уведомлений.")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

@dp.message(Moderator.waiting_for_news)
async def process_moderator_news(message: types.Message, state: FSMContext):
    try:
        # Публикуем новость в канал
        await bot.send_message(CHANNEL_CHAT_ID, f"📢 <b>Новость от модератора:</b>\n\n{message.text}", parse_mode=ParseMode.HTML)
        await message.answer("✅ Новость опубликована в канале!")
    except Exception as e:
        logger.error(f"Ошибка при публикации новости: {e}")
        await message.answer("❌ Произошла ошибка при публикации новости.")
    
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

@dp.message(ScheduleMonth.waiting_for_schedule)
async def process_schedule_month(message: types.Message, state: FSMContext):
    lines = message.text.strip().split('\n')
    entries = []
    errors = []
    for line in lines:
        if not line.strip():
            continue
        if ':' not in line:
            errors.append(f"Неверный формат строки: {line}")
            continue
        fio_part, date_part = line.split(':', 1)
        fio = fio_part.strip()
        date_str = date_part.strip()
        try:
            # Проверяем формат даты
            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            entries.append((fio, date_str))
        except Exception:
            errors.append(f"Неверный формат даты: {date_str} (ожидается ДД.ММ.ГГГГ)")
    if entries:
        # Добавляем каждую запись отдельно
        for fio, date_str in entries:
            await add_coffee_schedule_entry(fio, date_str, message.from_user.id)
        await message.answer(f"✅ График успешно сохранён! Количество записей: {len(entries)}")
    if errors:
        await message.answer("\n".join(errors))
    await state.clear()
    await send_main_menu(message, user_id=message.from_user.id)

async def sync_channel_with_excel():
    """Синхронизирует список подписчиков канала с Excel файлом"""
    try:
        import pandas as pd
        import os
        from pyrogram import Client
        
        if not CHANNEL_USERS_EXCEL or not os.path.exists(CHANNEL_USERS_EXCEL):
            logger.warning("Excel файл канала недоступен для синхронизации")
            return

        # Читаем Excel файл
        df = pd.read_excel(CHANNEL_USERS_EXCEL)
        logger.info(f"Channel sync: Excel loaded with {len(df)} rows")
        
        # Определяем колонку с ФИО
        fio_column = None
        for col in df.columns:
            if 'фио' in col.lower() or 'фio' in col.lower() or 'имя' in col.lower() or 'name' in col.lower():
                fio_column = col
                break
        
        if fio_column is None:
            fio_column = df.columns[0]
            logger.warning(f"Колонка с ФИО не найдена, используем: {fio_column}")
        
        # Получаем список разрешенных ФИО из Excel
        allowed_fios = set()
        for _, row in df.iterrows():
            fio = str(row[fio_column]).strip()
            if fio and fio.lower() not in ['nan', 'none', '']:
                allowed_fios.add(fio.lower())
        
        logger.info(f"Channel sync: {len(allowed_fios)} allowed FIOs from Excel")
        
        # Получаем текущих подписчиков из базы данных
        current_subscribers = await get_channel_subscribers()
        logger.info(f"Channel sync: {len(current_subscribers)} current subscribers")
        
        # Инициализируем Pyrogram клиент для управления каналом
        pyrogram_client = None
        try:
            # Проверяем, что переменные определены и настроены
            if ('PYROGRAM_API_ID' in globals() and 'PYROGRAM_API_HASH' in globals() and 'PYROGRAM_BOT_TOKEN' in globals() and
                PYROGRAM_API_ID != "your_api_id" and PYROGRAM_API_HASH != "your_api_hash" and PYROGRAM_BOT_TOKEN):
                
                pyrogram_client = Client(
                    "channel_manager",
                    api_id=int(PYROGRAM_API_ID),
                    api_hash=PYROGRAM_API_HASH,
                    bot_token=PYROGRAM_BOT_TOKEN
                )
                await pyrogram_client.start()
                logger.info("Pyrogram клиент для управления каналом запущен")
            else:
                logger.warning("Настройки Pyrogram не настроены. Запустите setup_pyrogram.py для настройки")
        except Exception as e:
            logger.error(f"Ошибка запуска Pyrogram клиента: {e}")
            pyrogram_client = None
        
        # Проверяем каждого подписчика
        removed_count = 0
        for user_id, username, fio, subscribed_at in current_subscribers:
            if fio and fio.lower() not in allowed_fios:
                # Пользователя нет в Excel - удаляем
                try:
                    # Удаляем из базы данных
                    await remove_channel_subscriber(user_id)
                    
                    # Удаляем из канала через Pyrogram
                    if pyrogram_client and CHANNEL_CHAT_ID:
                        try:
                            # Получаем информацию о пользователе
                            user_info = await pyrogram_client.get_users(user_id)
                            
                            # Удаляем пользователя из канала
                            await pyrogram_client.ban_chat_member(
                                chat_id=int(CHANNEL_CHAT_ID),  # Преобразуем в int
                                user_id=user_id
                            )
                            logger.info(f"Channel sync: removed user {user_id} ({fio}) from channel via Pyrogram")
                            
                            # Уведомляем пользователя через aiogram бота
                            try:
                                await bot.send_message(
                                    user_id,
                                    f"❌ <b>Доступ к каналу отозван</b>\n\n"
                                    f" <b>ФИО:</b> {fio}\n\n"
                                    f"<b>Причина:</b> Ваше ФИО было удалено из списка разрешенных пользователей.\n\n"
                                    f"Для восстановления доступа обратитесь к администратору.",
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                logger.error(f"Channel sync: error notifying user {user_id}: {e}")
                                
                        except Exception as channel_error:
                            logger.error(f"Channel sync: error removing user {user_id} from channel via Pyrogram: {channel_error}")
                    else:
                        logger.warning(f"Pyrogram клиент недоступен, пользователь {user_id} не удален из канала")
                    
                    removed_count += 1
                    
                except Exception as e:
                    logger.error(f"Channel sync: error processing user {user_id}: {e}")
        
        # Закрываем Pyrogram клиент
        if pyrogram_client:
            await pyrogram_client.stop()
            logger.info("Pyrogram клиент для управления каналом остановлен")
        
        if removed_count > 0:
            # Уведомляем администратора о синхронизации
            admin_message = (
                f"�� <b>Ежедневная синхронизация канала завершена</b>\n\n"
                f"📊 <b>Результаты:</b>\n"
                f"• Разрешено пользователей в Excel: {len(allowed_fios)}\n"
                f"• Текущих подписчиков: {len(current_subscribers)}\n"
                f"• Удалено пользователей: {removed_count}\n\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
            logger.info(f"Channel sync completed: {removed_count} users removed")
        else:
            logger.info("Channel sync completed: no users to remove")
            
    except Exception as e:
        logger.error(f"Ошибка синхронизации канала: {e}")
        # Уведомляем администратора об ошибке
        try:
            await bot.send_message(
                ADMIN_ID,
                f"❌ <b>Ошибка синхронизации канала</b>\n\n"
                f"🔍 <b>Ошибка:</b> {str(e)}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

async def periodic_channel_sync():
    """Периодическая синхронизация канала с Excel файлом (каждый день в 17:00)"""
    while True:
        try:
            # Получаем текущее время
            now = datetime.now()
            
            # Вычисляем время до следующей проверки (17:00)
            next_check = now.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # Если уже прошло 17:00, планируем на завтра
            if now.time() >= datetime.time(17, 0):
                next_check += timedelta(days=1)
            
            # Вычисляем время ожидания
            wait_seconds = (next_check - now).total_seconds()
            
            logger.info(f"Следующая синхронизация канала запланирована на {next_check.strftime('%d.%m.%Y %H:%M')}")
            logger.info(f"Ожидание {wait_seconds/3600:.1f} часов до следующей проверки")
            
            # Ждем до следующей проверки
            await asyncio.sleep(wait_seconds)
            
            logger.info("🕔 Запуск ежедневной синхронизации канала (17:00)...")
            await sync_channel_with_excel()
            logger.info("Ежедневная синхронизация канала завершена")
            
        except asyncio.CancelledError:
            logger.info("Периодическая синхронизация канала остановлена")
            break
        except Exception as e:
            logger.error(f"Ошибка периодической синхронизации канала: {e}")
            # Ждем час перед следующей попыткой
            await asyncio.sleep(60 * 60)

# Команда для ручной синхронизации канала
@dp.message(Command("sync_channel"))
async def sync_channel_command(message: types.Message):
    """Команда для ручной синхронизации канала с Excel файлом"""
    # Проверяем права администратора
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer("🔄 Запуск синхронизации канала с Excel файлом...")
    await sync_channel_with_excel()
    await message.answer("✅ Синхронизация канала завершена!")

@dp.message(Command("channel_status"))
async def channel_status_command(message: types.Message):
    """Команда для проверки статуса канала"""
    # Проверяем права администратора
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        import pandas as pd
        import os
        
        status_text = "📺 <b>Статус канала</b>\n\n"
        
        # Проверяем Excel файл
        if CHANNEL_USERS_EXCEL and os.path.exists(CHANNEL_USERS_EXCEL):
            df = pd.read_excel(CHANNEL_USERS_EXCEL)
            status_text += f"✅ Excel файл: {len(df)} пользователей\n"
        else:
            status_text += "❌ Excel файл недоступен\n"
        
        # Проверяем подписчиков в базе
        subscribers = await get_channel_subscribers()
        status_text += f"📊 Подписчиков в базе: {len(subscribers)}\n"
        
        # Проверяем настройки Pyrogram
        if ('PYROGRAM_API_ID' in globals() and 'PYROGRAM_API_HASH' in globals() and 'PYROGRAM_BOT_TOKEN' in globals() and
            PYROGRAM_API_ID != "your_api_id" and PYROGRAM_API_HASH != "your_api_hash" and PYROGRAM_BOT_TOKEN):
            status_text += "✅ Pyrogram настроен\n"
        else:
            status_text += "❌ Pyrogram не настроен (запустите setup_pyrogram.py)\n"
        
        # Проверяем ID канала
        if CHANNEL_CHAT_ID:
            status_text += f"📢 Канал: {CHANNEL_CHAT_ID}\n"
        else:
            status_text += "❌ ID канала не настроен\n"
        
        # Показываем последних подписчиков
        if subscribers:
            status_text += "\n👥 <b>Последние подписчики:</b>\n"
            for i, (user_id, username, fio) in enumerate(subscribers[:5], 1):
                status_text += f"{i}. {fio} (@{username or 'нет'})\n"
        
        await message.answer(status_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса канала: {e}")
        await message.answer(f"❌ Ошибка при проверке статуса: {e}")

# Обработчик заявок на вступление в канал
@dp.chat_join_request()
async def handle_chat_join_request(update: types.ChatJoinRequest):
    """Обработчик заявок на вступление в канал"""
    try:
        user_id = update.from_user.id
        username = update.from_user.username
        
        logger.info(f"Новая заявка на вступление в канал: user_id={user_id}, username={username}")
        
        # Всегда одобряем заявку временно, чтобы пользователь мог написать боту
        await update.approve()
        
        # Отправляем сообщение с запросом ФИО
        try:
            await bot.send_message(
                user_id,
                "👋 <b>Добро пожаловать!</b>\n\n"
                "Для завершения вступления в канал необходимо указать ваше ФИО.\n\n"
                "Пожалуйста, отправьте ваше полное имя (Фамилия Имя Отчество):",
                parse_mode=ParseMode.HTML
            )
            # Устанавливаем состояние FSM и pending_channel_request
            state = FSMContext(storage=dp.storage, chat_id=user_id, user_id=user_id)
            await state.set_state(ChannelSubscribe.waiting_for_fio)
            await state.update_data(pending_channel_request=True)
            
            # Уведомляем администратора о новой заявке
            admin_message = (
                f"🆕 <b>Новая заявка на вступление в канал</b>\n\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"👤 <b>Username:</b> @{username or 'Нет'}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⏳ <b>Статус:</b> Ожидает указания ФИО"
            )
            
            await bot.send_message(ADMIN_ID, admin_message, parse_mode=ParseMode.HTML)
            logger.info(f"Запрошено ФИО для user_id={user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка запроса ФИО для user_id={user_id}: {e}")
            # Если не удалось отправить сообщение, отклоняем заявку
            try:
                await update.decline()
            except:
                pass
            
    except Exception as e:
        logger.error(f"Ошибка обработки заявки на вступление в канал: {e}")
        try:
            await update.decline()
        except:
            pass

@dp.callback_query(lambda c: c.data == "get_invite_link")
async def get_invite_link_callback(callback_query: types.CallbackQuery):
    """Обработчик для получения пригласительной ссылки в канал"""
    # Проверяем права администратора
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
        return
    
    try:
        if INVITE_LINK and INVITE_LINK != "https://t.me/+your_invite_link_here":
            await callback_query.message.answer(
                f"🔗 <b>Пригласительная ссылка в канал</b>\n\n"
                f"📢 <b>Канал:</b> {CHANNEL_CHAT_ID}\n\n"
                f"🔗 <b>Ссылка:</b> {INVITE_LINK}\n\n"
                f"📋 <b>Инструкция:</b>\n"
                f"1. Поделитесь этой ссылкой с пользователями\n"
                f"2. При переходе по ссылке бот автоматически проверит ФИО\n"
                f"3. Если ФИО есть в Excel - заявка будет одобрена\n"
                f"4. Если ФИО нет - заявка будет отклонена\n"
                f"5. Дублирование ФИО не допускается",
                parse_mode=ParseMode.HTML
            )
        else:
            await callback_query.message.answer(
                "❌ <b>Пригласительная ссылка не настроена</b>\n\n"
                f"📢 <b>Канал:</b> {CHANNEL_CHAT_ID}\n\n"
                f"🔧 <b>Для настройки:</b>\n"
                f"1. Добавьте переменную INVITE_LINK в .env файл\n"
                f"2. Укажите актуальную ссылку-приглашение\n"
                f"3. Перезапустите бота",
                parse_mode=ParseMode.HTML
            )
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения пригласительной ссылки: {e}")
        await callback_query.answer("❌ Произошла ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data == "create_coffee_schedule")
async def create_coffee_schedule_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.edit_text(
            "📝 <b>Составление графика кофемашины</b>\n\n"
            "Отправьте график в формате:\n"
            "<code>ФИО1: ДД.ММ.ГГГГ\n"
            "ФИО2: ДД.ММ.ГГГГ\n"
            "ФИО3: ДД.ММ.ГГГГ</code>\n\n"
            "Пример:\n"
            "<code>Иванов Иван Иванович: 15.12.2024\n"
            "Петров Петр Петрович: 16.12.2024</code>",
            parse_mode=ParseMode.HTML
        )
        await state.set_state(CoffeeSchedule.waiting_for_schedule)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при создании графика кофе: {e}")
        await callback_query.answer("Произошла ошибка.", show_alert=True)

@dp.callback_query(lambda c: c.data == "view_coffee_schedule")
async def view_coffee_schedule_callback(callback_query: types.CallbackQuery):
    try:
        logger.info("Начинаем просмотр графика кофе...")
        schedule = await get_all_coffee_schedule()
        logger.info(f"Получено записей из графика кофе: {len(schedule)}")
        
        if not schedule:
            logger.info("График пуст")
            await callback_query.message.edit_text(
                "📊 <b>График кофемашины</b>\n\n"
                "График пуст.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Группируем по датам
        logger.info("Начинаем группировку по датам...")
        schedule_by_date = {}
        for i, entry in enumerate(schedule):
            logger.info(f"Обрабатываем запись {i}: {entry}")
            try:
                date = entry[2]  # date
                fio = entry[1]   # fio
                logger.info(f"Извлечены значения: date={repr(date)}, fio={repr(fio)}")
                
                # Пропускаем записи с пустыми датами
                if date is None or date == "":
                    logger.warning(f"Найдена запись с пустой датой для ФИО: {fio}")
                    continue
                    
                if date not in schedule_by_date:
                    schedule_by_date[date] = []
                schedule_by_date[date].append(fio)
                logger.info(f"Добавлена запись: {fio} на {date}")
            except Exception as e:
                logger.error(f"Ошибка при обработке записи {i}: {e}")
                continue
        
        if not schedule_by_date:
            await callback_query.message.edit_text(
                "📊 <b>График кофемашины</b>\n\n"
                "График пуст или содержит только записи с некорректными датами.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Дополнительная проверка на None значения перед сортировкой
        valid_dates = [date for date in schedule_by_date.keys() if date is not None]
        if not valid_dates:
            await callback_query.message.edit_text(
                "📊 <b>График кофемашины</b>\n\n"
                "График содержит только записи с некорректными датами.",
                parse_mode=ParseMode.HTML
            )
            return
        
        text = "📊 <b>График кофемашины:</b>\n\n"
        for date in sorted(valid_dates):
            text += f"📅 <b>{date}</b>\n"
            for fio in schedule_by_date[date]:
                text += f"  • {fio}\n"
            text += "\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data="coffee_schedule")
        keyboard.adjust(1)
        
        await callback_query.message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при просмотре графика кофе: {e}")
        await callback_query.answer("Произошла ошибка.", show_alert=True)

@dp.callback_query(lambda c: c.data == "clear_coffee_schedule")
async def clear_coffee_schedule_callback(callback_query: types.CallbackQuery):
    try:
        await clear_coffee_schedule()
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data="coffee_schedule")
        keyboard.adjust(1)
        
        await callback_query.message.edit_text(
            "🗑 <b>График кофемашины очищен</b>",
            reply_markup=keyboard.as_markup(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Ошибка при очистке графика кофе: {e}")
        await callback_query.answer("Произошла ошибка.", show_alert=True)

@dp.message(CoffeeSchedule.waiting_for_schedule)
async def process_coffee_schedule(message: types.Message, state: FSMContext):
    try:
        schedule_text = message.text.strip()
        lines = schedule_text.split('\n')
        
        entries = []
        errors = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            if ':' not in line:
                errors.append(f"Строка {i}: отсутствует двоеточие")
                continue
                
            fio, date_str = line.split(':', 1)
            fio = fio.strip()
            date_str = date_str.strip()
            
            if not fio:
                errors.append(f"Строка {i}: пустое ФИО")
                continue
                
            if not date_str:
                errors.append(f"Строка {i}: пустая дата")
                continue
            
            # Проверяем формат даты (ДД.ММ.ГГГГ)
            try:
                date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                formatted_date = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                errors.append(f"Строка {i}: неверный формат даты '{date_str}' (должно быть ДД.ММ.ГГГГ)")
                continue
            
            # Проверяем, что дата не в прошлом
            if date_obj.date() < datetime.now().date():
                errors.append(f"Строка {i}: дата '{date_str}' в прошлом")
                continue
            
            # Получаем user_id по ФИО
            user_id = await get_user_id_by_fio(fio)
            if not user_id:
                errors.append(f"Строка {i}: пользователь '{fio}' не найден в системе")
                continue
            
            entries.append((fio, formatted_date, user_id))
        
        if errors:
            error_text = "❌ <b>Ошибки в графике:</b>\n\n" + "\n".join(errors)
            await message.answer(error_text, parse_mode=ParseMode.HTML)
            return
        
        if not entries:
            await message.answer("❌ Не найдено корректных записей в графике.")
            await state.clear()
            return
        
        # Сохраняем записи в базу
        for fio, date, user_id in entries:
            await add_coffee_schedule_entry(fio, date, message.from_user.id, user_id)
        
        # Уведомляем всех участников графика
        notified_count = 0
        for fio, date, user_id in entries:
            try:
                await bot.send_message(
                    user_id,
                    f"☕ <b>Вас добавили в график кофемашины!</b>\n\n"
                    f"📅 <b>Дата:</b> {date}\n"
                    f"👤 <b>Ваше ФИО:</b> {fio}\n\n"
                    f"Не забудьте помыть кофемашину в указанную дату!",
                    parse_mode=ParseMode.HTML
                )
                notified_count += 1
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
        
        # Отмечаем, что уведомления отправлены
        schedule = await get_all_coffee_schedule()
        for entry in schedule:
            # Проверяем, что дата не None
            if entry[2] is None:
                logger.warning(f"Найдена запись с пустой датой при отметке уведомлений: entry_id={entry[0]}, fio={entry[1]}")
                continue
            if entry[1] in [e[0] for e in entries] and entry[2] in [e[1] for e in entries]:
                await mark_coffee_notification_sent(entry[0])
        
        success_text = (
            f"✅ <b>График кофемашины создан!</b>\n\n"
            f"📊 <b>Добавлено записей:</b> {len(entries)}\n"
            f"📨 <b>Уведомлений отправлено:</b> {notified_count}\n\n"
            f"Все участники графика получили уведомления в личные сообщения."
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 К управлению графиком", callback_data="coffee_schedule")
        keyboard.adjust(1)
        
        await message.answer(
            success_text,
            reply_markup=keyboard.as_markup(),
            parse_mode=ParseMode.HTML
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке графика кофе: {e}")
        await message.answer("❌ Произошла ошибка при обработке графика.")
        await state.clear()

async def check_today_coffee_schedule():
    """Проверяет график кофемашины на сегодня (выполняется в 11:00)"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        schedule = await get_today_coffee_schedule_for_notification()
        
        if not schedule:
            logger.info("📋 Проверка графика кофе в 11:00: нет записей на сегодня")
            return
        
        logger.info(f"📋 Проверка графика кофе в 11:00: найдено {len(schedule)} записей на сегодня")
        
        for entry in schedule:
            entry_id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at = entry
            logger.info(f"📋 Найдена запись: {fio} на {date} (user_id: {user_id})")
        
        logger.info("✅ Проверка графика кофе в 11:00 завершена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке графика кофе в 11:00: {e}")

async def send_coffee_notifications():
    """Отправляет уведомления о помывке кофемашины (выполняется в 16:00)"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        schedule = await get_today_coffee_schedule_for_notification()
        
        if not schedule:
            logger.info("📢 Отправка уведомлений о кофе в 16:00: нет записей на сегодня")
            return
        
        logger.info(f"📢 Отправка уведомлений о кофе в 16:00: найдено {len(schedule)} записей")
        
        sent_count = 0
        error_count = 0
        
        for entry in schedule:
            entry_id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at = entry
            
            # Ищем пользователя по ФИО в базе авторизованных пользователей
            user_info = await get_user_by_fio(fio)
            
            if not user_info:
                logger.warning(f"❌ Пользователь с ФИО '{fio}' не найден в базе авторизованных пользователей")
                error_count += 1
                continue
            
            user_id = user_info[0]  # user_id из базы авторизованных пользователей
            
            try:
                await bot.send_message(
                    user_id,
                    f"☕ <b>Уведомление о помывке кофемашины!</b>\n\n"
                    f"👤 <b>Ваше ФИО:</b> {fio}\n"
                    f"📅 <b>Сегодня:</b> {date}\n\n"
                    f"Сегодня ваша очередь мыть кофемашину! "
                    f"Пожалуйста, не забудьте выполнить эту обязанность.\n\n"
                    f"⏰ Время отправки: {datetime.now().strftime('%H:%M')}",
                    parse_mode=ParseMode.HTML
                )
                
                # Отмечаем, что уведомление отправлено
                await mark_coffee_notification_sent_by_fio(fio, date)
                
                logger.info(f"✅ Уведомление о кофе отправлено пользователю {user_id} ({fio})")
                sent_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id} ({fio}): {e}")
                error_count += 1
        
        logger.info(f"📢 Отправка уведомлений о кофе завершена: отправлено {sent_count}, ошибок {error_count}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомлений о кофе: {e}")

async def schedule_coffee_notifications():
    """Планировщик для ежедневных уведомлений о кофемашине"""
    logger.info("⏰ Запуск планировщика уведомлений о кофе (проверка в 11:00, отправка в 16:00)")
    
    while True:
        try:
            now = datetime.now()
            
            # Проверка в 11:00
            if now.hour == 11 and now.minute == 0:
                logger.info("🕐 11:00 - выполняем проверку графика кофе")
                await check_today_coffee_schedule()
                # Ждем 1 минуту, чтобы не выполнять проверку несколько раз
                await asyncio.sleep(60)
            
            # Отправка уведомлений в 16:00
            elif now.hour == 16 and now.minute == 0:
                logger.info("🕐 16:00 - отправляем уведомления о кофе")
                await send_coffee_notifications()
                # Ждем 1 минуту, чтобы не отправлять уведомления несколько раз
                await asyncio.sleep(60)
            else:
                # Проверяем каждую минуту
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике уведомлений о кофе: {e}")
            await asyncio.sleep(60)

@dp.message(Command("test_coffee_notification"))
async def test_coffee_notification_command(message: types.Message):
    """Команда для тестирования уведомлений о кофемашине"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("☕ Отправляем тестовые уведомления о кофемашине...")
        await send_coffee_notifications()
        await message.answer("✅ Тестовые уведомления отправлены!")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании уведомлений о кофе: {e}")
        await message.answer("❌ Произошла ошибка при отправке тестовых уведомлений.")

@dp.message(Command("test_coffee_check"))
async def test_coffee_check_command(message: types.Message):
    """Команда для тестирования проверки графика кофе"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("📋 Выполняем тестовую проверку графика кофе...")
        await check_today_coffee_schedule()
        await message.answer("✅ Тестовая проверка графика кофе завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании проверки графика кофе: {e}")
        await message.answer("❌ Произошла ошибка при проверке графика кофе.")

@dp.message(Command("send_coffee_notifications"))
async def send_coffee_notifications_command(message: types.Message):
    """Команда для ручной отправки уведомлений о кофе"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("☕ Отправляем уведомления о кофемашине...")
        await send_coffee_notifications()
        await message.answer("✅ Уведомления о кофемашине отправлены!")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о кофе: {e}")
        await message.answer("❌ Произошла ошибка при отправке уведомлений о кофе.")

@dp.message(Command("show_coffee_schedule"))
async def show_coffee_schedule_command(message: types.Message):
    """Команда для просмотра всего графика кофе"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("📋 Загружаем весь график кофе...")
        schedule = await get_all_coffee_schedule()
        
        if not schedule:
            await message.answer("📋 График кофе пуст.")
            return
        
        text = f"📋 <b>Весь график кофе ({len(schedule)} записей):</b>\n\n"
        
        for i, entry in enumerate(schedule, 1):
            entry_id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at = entry
            date_str = str(date) if date is not None else "NULL"
            text += f"{i}. <b>{fio}</b> - {date_str} (ID: {entry_id})\n"
        
        # Разбиваем на части, если текст слишком длинный
        if len(text) > 4096:
            parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
            for i, part in enumerate(parts):
                await message.answer(f"{part}\n\n<i>Часть {i+1}/{len(parts)}</i>", parse_mode=ParseMode.HTML)
        else:
            await message.answer(text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре графика кофе: {e}")
        await message.answer("❌ Произошла ошибка при просмотре графика кофе.")

@dp.message(Command("fix_coffee_dates"))
async def fix_coffee_dates_command(message: types.Message):
    """Команда для исправления NULL дат в графике кофе"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("🔧 Исправляем NULL даты в графике кофе...")
        fixed_count = await fix_null_dates_in_coffee_schedule()
        await message.answer(f"✅ Исправлено {fixed_count} записей с NULL датами!")
        
    except Exception as e:
        logger.error(f"Ошибка при исправлении дат в графике кофе: {e}")
        await message.answer("❌ Произошла ошибка при исправлении дат в графике кофе.")

@dp.message(Command("clean_coffee_schedule"))
async def clean_coffee_schedule_command(message: types.Message):
    """Команда для очистки некорректных записей графика кофе"""
    try:
        user_role = await get_user_role(message.from_user.id)
        if user_role not in ["admin", "moderator"]:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        await message.answer("🧹 Очищаем некорректные записи графика кофе...")
        await clean_invalid_coffee_entries()
        await message.answer("✅ Некорректные записи графика кофе очищены!")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке графика кофе: {e}")
        await message.answer("❌ Произошла ошибка при очистке графика кофе.")

@dp.message(Command("clear_keyboards"))
async def clear_keyboards_command(message: types.Message):
    """Команда для очистки старых клавиатур у всех пользователей"""
    if not await is_authorized(message.from_user.id):
        await message.answer("Для использования этой функции необходимо авторизоваться.")
        return
    
    role = await get_user_role(message.from_user.id)
    if role != 'admin':
        await message.answer("У вас нет прав для использования этой функции.")
        return
    
    await message.answer("🧹 Начинаем очистку старых клавиатур...")
    cleared_count = await clear_old_keyboards()
    await message.answer(f"✅ Очистка завершена! Обработано {cleared_count} пользователей.")

@dp.message(Command("cleanup_env"))
async def cleanup_env_command(message: types.Message):
    """Команда для очистки старых переменных ролей из .env файла"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        await cleanup_env_roles()
        await message.answer("✅ Старые переменные ролей удалены из .env файла")
    except Exception as e:
        logger.error(f"Ошибка при очистке .env файла: {e}")
        await message.answer("❌ Произошла ошибка при очистке .env файла.")

# Меню поиска с кнопкой "Назад"
def get_search_menu_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Поиск по ФИО", callback_data="search_by_fio")
    keyboard.button(text="🔍 Поиск по должности", callback_data="search_by_position")
    keyboard.button(text="🔍 Поиск по отделу", callback_data="search_by_department")
    keyboard.button(text="🔍 Поиск по телефону", callback_data="search_by_phone")
    keyboard.button(text="⬅️ Назад", callback_data="back_to_main")
    keyboard.adjust(2, 2, 1)
    return keyboard.as_markup()

# Обработчик возврата к меню поиска
@dp.callback_query(lambda c: c.data == "back_to_search_menu")
async def back_to_search_menu_callback(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "🔍 Поиск сотрудника\n\nВыберите тип поиска:",
        reply_markup=get_search_menu_keyboard()
    )
    await callback_query.answer()

# После результатов поиска показываем кнопку "Назад" (возврат к меню поиска)
def get_back_to_search_menu_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ Вернуться к поиску", callback_data="back_to_search_menu")
    return keyboard.as_markup()

# Обновляем process_search_fio
@dp.message(Search.waiting_for_fio)
async def process_search_fio(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    current_data = await state.get_data()
    logger.info(f"[SEARCH] user_id={message.from_user.id}, state={current_state}, data={current_data}, text={message.text}")
    await state.update_data(pending_channel_request=False)
    fio = message.text.strip()
    
    if not fio or len(fio) < 2:
        await message.answer(
            "❌ <b>Неверный запрос</b>\n\n"
            "Пожалуйста, введите ФИО для поиска (минимум 2 символа).",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
        await state.clear()
        return
    
    logger.info(f"Поиск по ФИО: user_id={message.from_user.id}, query='{fio}'")
    results = search_by_fio(data_manager.df, fio)
    
    if results.empty:
        await message.answer(
            f"❌ <b>Поиск по ФИО</b>\n\n"
            f"🔍 <b>Запрос:</b> {fio}\n"
            f"📊 <b>Результат:</b> Ничего не найдено\n\n"
            f"Попробуйте изменить запрос или использовать поиск по должности/отделу.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
    else:
        await message.answer(
            f"✅ <b>Поиск по ФИО</b>\n\n"
            f"🔍 <b>Запрос:</b> {fio}\n"
            f"📊 <b>Найдено:</b> {len(results)} сотрудников\n\n"
            f"Результаты поиска:",
            parse_mode=ParseMode.HTML
        )
        for idx, row in results.iterrows():
            caption = format_employee_caption(row)
            photo = getattr(row, 'Фото', None)
            if photo and isinstance(photo, str) and photo.lower() not in ('nan', 'none', ''):
                if photo.startswith("http://") or photo.startswith("https://"):
                    media = photo
                elif os.path.isfile(photo):
                    media = FSInputFile(photo)
                else:
                    media = photo
                try:
                    await message.answer_photo(photo=media, caption=caption, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.error(f"Ошибка при отправке фото «{photo}»: {e}")
                    await message.answer(caption, parse_mode=ParseMode.HTML)
            else:
                await message.answer(caption, parse_mode=ParseMode.HTML)
        # После результатов — кнопка назад
        await message.answer("⬅️ Вернуться к поиску", reply_markup=get_back_to_search_menu_keyboard())
    logger.info(f"Поиск по ФИО завершен: найдено {len(results)} результатов")
    await state.clear()

# Аналогично для поиска по должности
@dp.message(Search.waiting_for_position)
async def process_search_position(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    current_data = await state.get_data()
    logger.info(f"[SEARCH] user_id={message.from_user.id}, state={current_state}, data={current_data}, text={message.text}")
    await state.update_data(pending_channel_request=False)
    position = message.text.strip()
    
    if not position or len(position) < 2:
        await message.answer(
            "❌ <b>Неверный запрос</b>\n\n"
            "Пожалуйста, введите должность для поиска (минимум 2 символа).",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
        await state.clear()
        return
    
    logger.info(f"Поиск по должности: user_id={message.from_user.id}, query='{position}'")
    results = search_by_position(data_manager.df, position)
    
    if results.empty:
        await message.answer(
            f"❌ <b>Поиск по должности</b>\n\n"
            f"🔍 <b>Запрос:</b> {position}\n"
            f"📊 <b>Результат:</b> Ничего не найдено\n\n"
            f"Попробуйте изменить запрос или использовать поиск по ФИО/отделу.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
    else:
        await message.answer(
            f"✅ <b>Поиск по должности</b>\n\n"
            f"🔍 <b>Запрос:</b> {position}\n"
            f"📊 <b>Найдено:</b> {len(results)} сотрудников\n\n"
            f"Результаты поиска:",
            parse_mode=ParseMode.HTML
        )
        for idx, row in results.iterrows():
            caption = format_employee_caption(row)
            photo = getattr(row, 'Фото', None)
            if photo and isinstance(photo, str) and photo.lower() not in ('nan', 'none', ''):
                if photo.startswith("http://") or photo.startswith("https://"):
                    media = photo
                elif os.path.isfile(photo):
                    media = FSInputFile(photo)
                else:
                    media = photo
                try:
                    await message.answer_photo(photo=media, caption=caption, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.error(f"Ошибка при отправке фото «{photo}»: {e}")
                    await message.answer(caption, parse_mode=ParseMode.HTML)
            else:
                await message.answer(caption, parse_mode=ParseMode.HTML)
        await message.answer("⬅️ Вернуться к поиску", reply_markup=get_back_to_search_menu_keyboard())
    logger.info(f"Поиск по должности завершен: найдено {len(results)} результатов")
    await state.clear()

# Аналогично для поиска по отделу
@dp.message(Search.waiting_for_department)
async def process_search_department(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    current_data = await state.get_data()
    logger.info(f"[SEARCH] user_id={message.from_user.id}, state={current_state}, data={current_data}, text={message.text}")
    await state.update_data(pending_channel_request=False)
    department = message.text.strip()
    
    if not department or len(department) < 2:
        await message.answer(
            "❌ <b>Неверный запрос</b>\n\n"
            "Пожалуйста, введите отдел для поиска (минимум 2 символа).",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
        await state.clear()
        return
    
    logger.info(f"Поиск по отделу: user_id={message.from_user.id}, query='{department}'")
    results = search_by_department(data_manager.df, department)
    
    if results.empty:
        await message.answer(
            f"❌ <b>Поиск по отделу</b>\n\n"
            f"🔍 <b>Запрос:</b> {department}\n"
            f"📊 <b>Результат:</b> Ничего не найдено\n\n"
            f"Попробуйте изменить запрос или использовать поиск по ФИО/должности.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_to_search_menu_keyboard()
        )
    else:
        await message.answer(
            f"✅ <b>Поиск по отделу</b>\n\n"
            f"🔍 <b>Запрос:</b> {department}\n"
            f"📊 <b>Найдено:</b> {len(results)} сотрудников\n\n"
            f"Результаты поиска:",
            parse_mode=ParseMode.HTML
        )
        for idx, row in results.iterrows():
            caption = format_employee_caption(row)
            photo = getattr(row, 'Фото', None)
            if photo and isinstance(photo, str) and photo.lower() not in ('nan', 'none', ''):
                if photo.startswith("http://") or photo.startswith("https://"):
                    media = photo
                elif os.path.isfile(photo):
                    media = FSInputFile(photo)
                else:
                    media = photo
                try:
                    await message.answer_photo(photo=media, caption=caption, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.error(f"Ошибка при отправке фото «{photo}»: {e}")
                    await message.answer(caption, parse_mode=ParseMode.HTML)
            else:
                await message.answer(caption, parse_mode=ParseMode.HTML)
        await message.answer("⬅️ Вернуться к поиску", reply_markup=get_back_to_search_menu_keyboard())
    logger.info(f"Поиск по отделу завершен: найдено {len(results)} результатов")
    await state.clear()

@dp.callback_query(lambda c: c.data == "download_contacts")
async def download_contacts_callback(callback_query: types.CallbackQuery):
    try:
        import tempfile
        df = data_manager.df
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            await callback_query.message.answer_document(
                FSInputFile(tmp_file.name, filename="contacts.xlsx"), 
                caption="Актуальные контакты"
            )
        os.unlink(tmp_file.name)
        await callback_query.answer("Контакты отправлены!")
    except Exception as e:
        logger.error(f"Ошибка при скачивании контактов: {e}")
        await callback_query.answer("Произошла ошибка при скачивании контактов.", show_alert=True)



# === ЗАПУСК БОТА ===

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
        logger.info("Бот остановлен пользователем (KeyboardInterrupt)")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}")
    finally:
        print("Завершение работы бота")
        logger.info("Завершение работы бота") 
