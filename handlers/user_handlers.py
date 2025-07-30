"""
Обработчики для обычных пользователей
"""

import logging
import pandas as pd
import os
from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import CHANNEL_USERS_EXCEL, ADMIN_ID, CHANNEL_CHAT_ID
from database import *
from keyboards import *
from states import AuthorizeUser, ProposeNews, MessageUser, Search
from utils import escape_html, validate_fio
from services import ExcelService

logger = logging.getLogger(__name__)


# ============= ОБРАБОТЧИКИ АВТОРИЗАЦИИ =============

async def request_auth_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик запроса авторизации"""
    is_auth = await is_authorized(callback_query.from_user.id)
    
    if is_auth:
        await callback_query.answer("Вы уже авторизованы!", show_alert=True)
        # Импортируем здесь, чтобы избежать циклических импортов
        from handlers.common_handlers import send_main_menu
        await send_main_menu(callback_query.message, user_id=callback_query.from_user.id)
        return
    
    await callback_query.answer()
    await callback_query.message.answer(
        "👋 <b>Авторизация в корпоративном боте</b>\n\n"
        "Для использования функций необходимо авторизоваться.\n\n"
        "Пожалуйста, введите ваше ФИО (Фамилия Имя Отчество):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AuthorizeUser.waiting_for_fio)


async def bot_info_callback(callback_query: types.CallbackQuery):
    """Обработчик информации о боте"""
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


async def process_fio(message: types.Message, state: FSMContext):
    """Обработка ввода ФИО при авторизации"""
    fio = message.text.strip()
    
    # Проверяем формат ФИО
    if not validate_fio(fio):
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
        f"👤 <b>Ваше ФИО:</b> {escape_html(fio)}\n\n"
        "Теперь введите вашу должность:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AuthorizeUser.waiting_for_position)


async def process_position(message: types.Message, state: FSMContext):
    """Обработка ввода должности при авторизации"""
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
            
            # Проверяем наличие пользователя
            for index, row in df.iterrows():
                excel_fio = str(row[fio_column]).strip().lower()
                user_fio = fio.lower()
                
                if excel_fio == user_fio or user_fio in excel_fio or excel_fio in user_fio:
                    user_found_in_excel = True
                    logger.info(f"Пользователь найден в Excel: {fio}")
                    break
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке Excel файла канала: {e}")
    
    # Сохраняем заявку на авторизацию
    try:
        user = message.from_user
        await add_auth_request(
            user_id=user.id,
            username=user.username or "",
            fio=fio,
            position=position
        )
        
        logger.info(f"Заявка на авторизацию сохранена: user_id={user.id}, fio={fio}")
        
        # Отправляем уведомление администратору
        try:
            from aiogram import Bot
            from config import BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)
            
            admin_message = (
                f"📋 <b>Новая заявка на авторизацию</b>\n\n"
                f"👤 <b>ФИО:</b> {escape_html(fio)}\n"
                f"💼 <b>Должность:</b> {escape_html(position)}\n"
                f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
                f"📱 <b>Username:</b> @{user.username or 'не указан'}\n"
                f"📊 <b>Найден в Excel:</b> {'✅ Да' if user_found_in_excel else '❌ Нет'}\n\n"
                f"📅 <b>Время:</b> {message.date.strftime('%d.%m.%Y %H:%M')}"
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard_builder = InlineKeyboardBuilder()
            keyboard_builder.add(types.InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user.id}"))
            keyboard_builder.add(types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{user.id}"))
            keyboard_builder.adjust(2)
            keyboard = keyboard_builder.as_markup()
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
        
        # Отправляем подтверждение пользователю
        await message.answer(
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"👤 <b>ФИО:</b> {escape_html(fio)}\n"
            f"💼 <b>Должность:</b> {escape_html(position)}\n\n"
            "⏳ Ваша заявка отправлена администратору на рассмотрение.\n"
            "Вы получите уведомление о принятом решении.",
            parse_mode=ParseMode.HTML
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении заявки: {e}")
        await message.answer(
            "❌ <b>Ошибка при отправке заявки</b>\n\n"
            "Произошла ошибка при сохранении заявки. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


# ============= ПОЛЬЗОВАТЕЛЬСКИЕ ФУНКЦИИ =============

async def search_employees_callback(callback_query: types.CallbackQuery):
    """Обработчик поиска сотрудников"""
    keyboard = create_search_keyboard()
    await callback_query.message.answer(
        "🔍 <b>Поиск сотрудников</b>\n\nВыберите тип поиска:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()


async def download_contacts_callback(callback_query: types.CallbackQuery):
    """Обработчик скачивания контактов"""
    try:
        excel_service = ExcelService()
        
        # Получаем информацию о файле
        info = excel_service.get_column_info()
        
        if not info:
            await callback_query.answer("❌ Excel файл недоступен", show_alert=True)
            return
        
        # Отправляем файл пользователю
        try:
            from aiogram.types import FSInputFile
            
            file = FSInputFile(excel_service.file_path, filename="contacts.xlsx")
            
            caption = (
                f"📥 <b>База контактов</b>\n\n"
                f"📊 <b>Записей:</b> {info.get('row_count', 0)}\n"
                f"📋 <b>Колонок:</b> {info.get('column_count', 0)}\n"
                f"📅 <b>Дата:</b> {message.date.strftime('%d.%m.%Y %H:%M')}"
            )
            
            await callback_query.message.answer_document(
                file,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"Файл контактов отправлен пользователю {callback_query.from_user.id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            await callback_query.answer("❌ Ошибка при отправке файла", show_alert=True)
    
    except Exception as e:
        logger.error(f"Ошибка скачивания контактов: {e}")
        await callback_query.answer("❌ Ошибка при подготовке файла", show_alert=True)


async def propose_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик предложения новости"""
    await callback_query.answer()
    await callback_query.message.answer(
        "📝 <b>Предложение новости</b>\n\n"
        "Введите текст новости, которую хотите предложить:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ProposeNews.waiting_for_news)


async def process_news_proposal(message: types.Message, state: FSMContext):
    """Обработка предложения новости"""
    news_text = message.text.strip()
    
    if not news_text or len(news_text) < 10:
        await message.answer(
            "❌ <b>Слишком короткий текст</b>\n\n"
            "Пожалуйста, введите более подробный текст новости (минимум 10 символов).",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        # Сохраняем предложение новости
        proposal_id = await add_news_proposal(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            fio=message.from_user.full_name or "Неизвестно",
            news_text=news_text,
            photos_json=""
        )
        
        # Отправляем подтверждение
        await message.answer(
            "✅ <b>Новость предложена!</b>\n\n"
            f"📝 <b>Ваше предложение:</b>\n{escape_html(news_text[:200])}{'...' if len(news_text) > 200 else ''}\n\n"
            "⏳ Предложение отправлено на модерацию.",
            parse_mode=ParseMode.HTML
        )
        
        # Уведомляем модераторов/администраторов
        try:
            from aiogram import Bot
            from config import BOT_TOKEN, MODERATOR_ID, MARKETER_ID
            bot = Bot(token=BOT_TOKEN)
            
            notification_text = (
                f"📝 <b>Новое предложение новости</b>\n\n"
                f"👤 <b>Автор:</b> {escape_html(message.from_user.full_name or 'Неизвестно')}\n"
                f"🆔 <b>User ID:</b> <code>{message.from_user.id}</code>\n\n"
                f"📄 <b>Текст:</b>\n{escape_html(news_text[:300])}{'...' if len(news_text) > 300 else ''}\n\n"
                f"📅 <b>Время:</b> {message.date.strftime('%d.%m.%Y %H:%M')}"
            )
            
            keyboard = create_news_approval_keyboard(proposal_id)
            
            # Отправляем админу
            await bot.send_message(ADMIN_ID, notification_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            
            # Отправляем модератору и маркетологу, если они есть
            for user_id in [MODERATOR_ID, MARKETER_ID]:
                if user_id and user_id != 0:
                    try:
                        await bot.send_message(user_id, notification_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о новости: {e}")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении предложения новости: {e}")
        await message.answer(
            "❌ <b>Ошибка</b>\n\nПроизошла ошибка при сохранении предложения. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


# ============= ОБРАБОТЧИКИ ПОИСКА =============

async def search_by_fio_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик поиска по ФИО"""
    await callback_query.answer()
    await callback_query.message.answer(
        "👤 <b>Поиск по ФИО</b>\n\n"
        "Введите ФИО или часть ФИО для поиска:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Search.waiting_for_fio)


async def search_by_position_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик поиска по должности"""
    await callback_query.answer()
    await callback_query.message.answer(
        "💼 <b>Поиск по должности</b>\n\n"
        "Введите должность или её часть для поиска:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Search.waiting_for_position)


async def search_by_department_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик поиска по отделу"""
    await callback_query.answer()
    await callback_query.message.answer(
        "🏢 <b>Поиск по отделу</b>\n\n"
        "Введите название отдела или его часть для поиска:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Search.waiting_for_department)


async def process_search_fio(message: types.Message, state: FSMContext):
    """Обработка поиска по ФИО"""
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer(
            "❌ <b>Слишком короткий запрос</b>\n\n"
            "Введите минимум 2 символа для поиска.",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        excel_service = ExcelService()
        results = excel_service.search_by_fio(query)
        
        if not results:
            await message.answer(
                f"❌ <b>Ничего не найдено</b>\n\n"
                f"По запросу <i>'{escape_html(query)}'</i> сотрудники не найдены.",
                parse_mode=ParseMode.HTML
            )
        else:
            # Формируем результаты поиска
            text = f"🔍 <b>Результаты поиска по ФИО</b>\n"
            text += f"📝 <b>Запрос:</b> {escape_html(query)}\n"
            text += f"📊 <b>Найдено:</b> {len(results)} сотрудник(ов)\n\n"
            
            for i, result in enumerate(results[:10], 1):  # Показываем первые 10
                fio = result.get('ФИО', 'Не указано')
                position = result.get('Должность', 'Не указано')
                department = result.get('Отдел', 'Не указано')
                phone = result.get('Номер Телефона', result.get('Телефон', 'Не указано'))
                photo = result.get('Фото', '')
                
                text += f"<b>{i}.</b> 👤 <b>{escape_html(str(fio))}</b>\n"
                text += f"💼 {escape_html(str(position))}\n"
                if str(department) != 'Не указано':
                    text += f"🏢 {escape_html(str(department))}\n"
                if str(phone) != 'Не указано':
                    text += f"📞 {escape_html(str(phone))}\n"
                if photo and str(photo) != 'nan':
                    text += f"📷 <b>Фото:</b> {escape_html(str(photo))}\n"
                text += "\n"
            
            if len(results) > 10:
                text += f"... и ещё {len(results) - 10} результат(ов)"
            
            # Создаем клавиатуру с кнопкой "Назад"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(text="⬅️ Назад к поиску", callback_data="search_employees"))
            builder.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
            builder.adjust(1)
            keyboard = builder.as_markup()
            
            await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка поиска по ФИО: {e}")
        await message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Произошла ошибка при поиске. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


async def process_search_position(message: types.Message, state: FSMContext):
    """Обработка поиска по должности"""
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer(
            "❌ <b>Слишком короткий запрос</b>\n\n"
            "Введите минимум 2 символа для поиска.",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        excel_service = ExcelService()
        results = excel_service.search_by_position(query)
        
        if not results:
            await message.answer(
                f"❌ <b>Ничего не найдено</b>\n\n"
                f"По должности <i>'{escape_html(query)}'</i> сотрудники не найдены.",
                parse_mode=ParseMode.HTML
            )
        else:
            # Формируем результаты поиска
            text = f"🔍 <b>Результаты поиска по должности</b>\n"
            text += f"📝 <b>Запрос:</b> {escape_html(query)}\n"
            text += f"📊 <b>Найдено:</b> {len(results)} сотрудник(ов)\n\n"
            
            for i, result in enumerate(results[:10], 1):  # Показываем первые 10
                fio = result.get('ФИО', 'Не указано')
                position = result.get('Должность', 'Не указано')
                department = result.get('Отдел', 'Не указано')
                phone = result.get('Номер Телефона', result.get('Телефон', 'Не указано'))
                photo = result.get('Фото', '')
                
                text += f"<b>{i}.</b> 👤 <b>{escape_html(str(fio))}</b>\n"
                text += f"💼 {escape_html(str(position))}\n"
                if str(department) != 'Не указано':
                    text += f"🏢 {escape_html(str(department))}\n"
                if str(phone) != 'Не указано':
                    text += f"📞 {escape_html(str(phone))}\n"
                if photo and str(photo) != 'nan':
                    text += f"📷 <b>Фото:</b> {escape_html(str(photo))}\n"
                text += "\n"
            
            if len(results) > 10:
                text += f"... и ещё {len(results) - 10} результат(ов)"
            
            # Создаем клавиатуру с кнопкой "Назад"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(text="⬅️ Назад к поиску", callback_data="search_employees"))
            builder.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
            builder.adjust(1)
            keyboard = builder.as_markup()
            
            await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка поиска по должности: {e}")
        await message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Произошла ошибка при поиске. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


async def process_search_department(message: types.Message, state: FSMContext):
    """Обработка поиска по отделу"""
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer(
            "❌ <b>Слишком короткий запрос</b>\n\n"
            "Введите минимум 2 символа для поиска.",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        excel_service = ExcelService()
        results = excel_service.search_by_department(query)
        
        if not results:
            await message.answer(
                f"❌ <b>Ничего не найдено</b>\n\n"
                f"В отделе <i>'{escape_html(query)}'</i> сотрудники не найдены.",
                parse_mode=ParseMode.HTML
            )
        else:
            # Формируем результаты поиска
            text = f"🔍 <b>Результаты поиска по отделу</b>\n"
            text += f"📝 <b>Запрос:</b> {escape_html(query)}\n"
            text += f"📊 <b>Найдено:</b> {len(results)} сотрудник(ов)\n\n"
            
            for i, result in enumerate(results[:10], 1):  # Показываем первые 10
                fio = result.get('ФИО', 'Не указано')
                position = result.get('Должность', 'Не указано')
                department = result.get('Отдел', 'Не указано')
                phone = result.get('Номер Телефона', result.get('Телефон', 'Не указано'))
                photo = result.get('Фото', '')
                
                text += f"<b>{i}.</b> 👤 <b>{escape_html(str(fio))}</b>\n"
                text += f"💼 {escape_html(str(position))}\n"
                if str(department) != 'Не указано':
                    text += f"🏢 {escape_html(str(department))}\n"
                if str(phone) != 'Не указано':
                    text += f"📞 {escape_html(str(phone))}\n"
                if photo and str(photo) != 'nan':
                    text += f"📷 <b>Фото:</b> {escape_html(str(photo))}\n"
                text += "\n"
            
            if len(results) > 10:
                text += f"... и ещё {len(results) - 10} результат(ов)"
            
            # Создаем клавиатуру с кнопкой "Назад"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(text="⬅️ Назад к поиску", callback_data="search_employees"))
            builder.add(types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
            builder.adjust(1)
            keyboard = builder.as_markup()
            
            await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка поиска по отделу: {e}")
        await message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Произошла ошибка при поиске. Попробуйте позже.",
            parse_mode=ParseMode.HTML
        )


def register_user_handlers(dp: Dispatcher):
    """Регистрирует обработчики для пользователей"""
    
    # Обработчики авторизации
    dp.callback_query.register(
        request_auth_callback,
        lambda c: c.data == "request_auth"
    )
    
    dp.callback_query.register(
        bot_info_callback,
        lambda c: c.data == "bot_info"
    )
    
    dp.message.register(
        process_fio,
        AuthorizeUser.waiting_for_fio
    )
    
    dp.message.register(
        process_position,
        AuthorizeUser.waiting_for_position
    )
    
    # Пользовательские функции
    dp.callback_query.register(
        search_employees_callback,
        lambda c: c.data == "search_employees"
    )
    
    dp.callback_query.register(
        download_contacts_callback,
        lambda c: c.data == "download_contacts"
    )
    
    dp.callback_query.register(
        propose_news_callback,
        lambda c: c.data == "propose_news"
    )
    
    dp.message.register(
        process_news_proposal,
        ProposeNews.waiting_for_news
    )
    
    # Обработчики поиска
    dp.callback_query.register(
        search_by_fio_callback,
        lambda c: c.data == "search_by_fio"
    )
    
    dp.callback_query.register(
        search_by_position_callback,
        lambda c: c.data == "search_by_position"
    )
    
    dp.callback_query.register(
        search_by_department_callback,
        lambda c: c.data == "search_by_department"
    )
    
    dp.message.register(
        process_search_fio,
        Search.waiting_for_fio
    )
    
    dp.message.register(
        process_search_position,
        Search.waiting_for_position
    )
    
    dp.message.register(
        process_search_department,
        Search.waiting_for_department
    ) 