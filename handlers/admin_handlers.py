"""
Обработчики для администраторов
"""

import logging
from datetime import datetime
from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_ID, CHANNEL_CHAT_ID
from database import *
from keyboards import *
from states import DeleteRequest, AddUser, AssignRole, RemoveUser, Notify
from utils import escape_html, admin_required
from services import SyncService, NotificationService

logger = logging.getLogger(__name__)


# ============= ПАНЕЛЬ АДМИНИСТРАТОРА =============

async def admin_panel_callback(callback_query: types.CallbackQuery):
    """Обработчик админ панели"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для доступа к админ панели.", show_alert=True)
        return
    
    keyboard = create_admin_panel_keyboard()
    await callback_query.message.edit_text(
        "👑 <b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()


# ============= УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =============

async def view_users_callback(callback_query: types.CallbackQuery):
    """Обработчик просмотра пользователей"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для просмотра пользователей.", show_alert=True)
        return
    
    try:
        logger.info(f"Запрос на просмотр пользователей от {callback_query.from_user.id}")
        users = await get_authorized_users()
        logger.info(f"Получено {len(users)} пользователей из базы данных")
        
        if not users:
            await callback_query.message.answer("👥 Нет авторизованных пользователей.")
            await callback_query.answer()
            return

        text = "👥 <b>Авторизованные пользователи:</b>\n\n"
        for i, user in enumerate(users[:20], 1):  # Показываем первые 20
            try:
                user_id, username, fio, position, role = user
                
                # Экранируем HTML-символы
                safe_fio = escape_html(fio)
                safe_username = escape_html(username) if username else 'Нет'
                safe_position = escape_html(position)
                safe_role = escape_html(role) if role else 'user'
                
                text += f"<b>{i}.</b> 👤 <b>{safe_fio}</b>\n"
                text += f"🆔 ID: <code>{user_id}</code>\n"
                text += f"📱 @{safe_username}\n"
                text += f"💼 {safe_position}\n"
                text += f"👑 Роль: {safe_role}\n\n"
                
            except Exception as user_error:
                logger.error(f"Ошибка обработки пользователя {user}: {user_error}")
                continue
        
        if len(users) > 20:
            text += f"... и ещё {len(users) - 20} пользователей"
        
        await callback_query.message.answer(text, parse_mode=ParseMode.HTML)
        await callback_query.answer(f"Найдено {len(users)} пользователей")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре пользователей: {e}")
        await callback_query.answer("Произошла ошибка при загрузке пользователей.", show_alert=True)


async def view_requests_callback(callback_query: types.CallbackQuery):
    """Обработчик просмотра заявок"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для просмотра заявок.", show_alert=True)
        return
    
    try:
        requests = await get_pending_requests()
        
        if not requests:
            await callback_query.message.answer("📋 Нет заявок на авторизацию.")
            await callback_query.answer()
            return
        
        text = "📋 <b>Заявки на авторизацию:</b>\n\n"
        
        for i, request in enumerate(requests[:10], 1):  # Показываем первые 10
            try:
                # auth_requests содержит: user_id, username, fio, position, timestamp
                if len(request) >= 4:
                    user_id, username, fio, position = request[:4]
                    timestamp = request[4] if len(request) > 4 else "Не указана"
                else:
                    continue
                
                safe_fio = escape_html(fio)
                safe_username = escape_html(username) if username else 'Нет'
                safe_position = escape_html(position)
                
                text += f"<b>{i}. Заявка</b>\n"
                text += f"👤 <b>ФИО:</b> {safe_fio}\n"
                text += f"💼 <b>Должность:</b> {safe_position}\n"
                text += f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                text += f"📱 <b>Username:</b> @{safe_username}\n"
                text += f"📅 <b>Дата:</b> {timestamp}\n\n"
                
            except Exception as req_error:
                logger.error(f"Ошибка обработки заявки {request}: {req_error}")
                continue
        
        if len(requests) > 10:
            text += f"... и ещё {len(requests) - 10} заявок"
        
        await callback_query.message.answer(text, parse_mode=ParseMode.HTML)
        await callback_query.answer(f"Найдено {len(requests)} заявок")
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре заявок: {e}")
        await callback_query.answer("Произошла ошибка при загрузке заявок.", show_alert=True)


async def assign_role_callback(callback_query: types.CallbackQuery):
    """Обработчик назначения ролей - показывает список пользователей с пагинацией"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для назначения ролей.", show_alert=True)
        return
    
    try:
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
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        keyboard = InlineKeyboardBuilder()
        
        # Кнопки для каждого пользователя
        for i, user in enumerate(page_users):
            user_id, username, fio, position, role = user
            user_num = start_idx + i + 1
            
            # Кнопка для выбора пользователя
            keyboard.add(types.InlineKeyboardButton(
                text=f"👤 {user_num}. {fio[:20]}{'...' if len(fio) > 20 else ''}",
                callback_data=f"select_user_{user_id}"
            ))
        
        # Кнопки навигации
        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"users_page_{page - 1}"
            ))
        if page < total_pages - 1:
            nav_row.append(types.InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"users_page_{page + 1}"
            ))
        
        if nav_row:
            keyboard.row(*nav_row)
        
        # Кнопка возврата в админ панель
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад в админ панель",
            callback_data="admin_panel"
        ))
        
        # Настройка расположения кнопок
        keyboard.adjust(1)  # По одной кнопке в ряду для пользователей
        
        await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при показе страницы пользователей: {e}")
        await message.answer("Произошла ошибка при отображении пользователей.")


# ============= ОДОБРЕНИЕ/ОТКЛОНЕНИЕ ЗАЯВОК =============

async def approve_user_callback(callback_query: types.CallbackQuery):
    """Обработчик одобрения пользователя"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для одобрения пользователей.", show_alert=True)
        return
    
    # Проверяем, что это не approve_news_
    if callback_query.data.startswith("approve_news_"):
        logger.debug("CALLBACK: approve_news detected, skipping user approval handler")
        return
    
    try:
        # Парсим user_id из callback_data
        user_id = int(callback_query.data.split("_")[1])
        
        # Одобряем пользователя
        success = await approve_user(user_id)
        
        if success:
            await callback_query.answer("✅ Пользователь одобрен!", show_alert=True)
            
            # Уведомляем пользователя
            try:
                from aiogram import Bot
                from config import BOT_TOKEN
                bot = Bot(token=BOT_TOKEN)
                
                await bot.send_message(
                    user_id,
                    "✅ <b>Ваша заявка одобрена!</b>\n\n"
                    "Добро пожаловать в корпоративный бот! 🎉\n"
                    "Теперь вы можете использовать все функции бота.\n\n"
                    "Для начала работы отправьте /start",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
            
            # Логируем действие
            await log_admin_action(callback_query.from_user.id, f"approved_user_{user_id}")
        else:
            await callback_query.answer("❌ Ошибка при одобрении пользователя", show_alert=True)
    
    except Exception as e:
        logger.error(f"Ошибка одобрения пользователя: {e}")
        await callback_query.answer("❌ Ошибка при одобрении", show_alert=True)


async def decline_user_callback(callback_query: types.CallbackQuery):
    """Обработчик отклонения пользователя"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для отклонения пользователей.", show_alert=True)
        return
    
    try:
        # Парсим user_id из callback_data
        user_id = int(callback_query.data.split("_")[1])
        
        # Отклоняем пользователя
        success = await decline_user(user_id)
        
        if success:
            await callback_query.answer("❌ Пользователь отклонен!", show_alert=True)
            
            # Уведомляем пользователя
            try:
                from aiogram import Bot
                from config import BOT_TOKEN
                bot = Bot(token=BOT_TOKEN)
                
                await bot.send_message(
                    user_id,
                    "❌ <b>Ваша заявка отклонена</b>\n\n"
                    "К сожалению, ваша заявка на авторизацию была отклонена.\n"
                    "Для получения дополнительной информации обратитесь к администратору.",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")
            
            # Логируем действие
            await log_admin_action(callback_query.from_user.id, f"declined_user_{user_id}")
        else:
            await callback_query.answer("❌ Ошибка при отклонении пользователя", show_alert=True)
    
    except Exception as e:
        logger.error(f"Ошибка отклонения пользователя: {e}")
        await callback_query.answer("❌ Ошибка при отклонении", show_alert=True)


# ============= СИНХРОНИЗАЦИЯ =============

async def sync_data_callback(callback_query: types.CallbackQuery):
    """Обработчик синхронизации данных"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для синхронизации.", show_alert=True)
        return
    
    await callback_query.message.answer("🔄 Синхронизация данных...")
    
    try:
        sync_service = SyncService()
        result = await sync_service.sync_database()
        
        if result['success']:
            stats = result['stats']
            report = "🔄 <b>Отчет о синхронизации базы данных</b>\n\n"
            report += f"✅ Пользователи: {stats.get('users_count', 0)} записей\n"
            report += f"✅ Заявки: {stats.get('requests_count', 0)} записей\n"
            report += f"✅ Новости: {stats.get('news_count', 0)} записей\n\n"
            report += f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        else:
            report = f"❌ <b>Ошибка синхронизации:</b>\n{result.get('error', 'Неизвестная ошибка')}"
        
        await callback_query.message.answer(report, parse_mode=ParseMode.HTML)
        await callback_query.answer("Синхронизация завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        await callback_query.message.answer(f"❌ Ошибка синхронизации: {e}")
        await callback_query.answer("Ошибка синхронизации", show_alert=True)


async def sync_bitrix24_callback(callback_query: types.CallbackQuery):
    """Обработчик синхронизации с Bitrix24"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
        return
    
    await callback_query.message.answer("🔄 Запуск синхронизации с Bitrix24...")
    
    try:
        sync_service = SyncService()
        result = await sync_service.sync_with_bitrix24()
        
        if result['success']:
            success_msg = "✅ <b>Синхронизация завершена успешно!</b>\n\n"
            success_msg += f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            await callback_query.message.answer(success_msg, parse_mode=ParseMode.HTML)
        else:
            error_msg = f"❌ <b>Ошибка синхронизации:</b>\n{result.get('error', 'Неизвестная ошибка')}"
            await callback_query.message.answer(error_msg, parse_mode=ParseMode.HTML)
    
    except Exception as e:
        logger.error(f"Ошибка синхронизации с Bitrix24: {e}")
        await callback_query.message.answer(f"❌ Ошибка синхронизации: {e}")
    
    await callback_query.answer()


# ============= УВЕДОМЛЕНИЯ =============

async def send_notification_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик отправки уведомлений"""
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ У вас нет прав для отправки уведомлений.", show_alert=True)
        return
    
    await callback_query.message.answer("📢 <b>Отправка уведомления</b>\n\nВведите текст уведомления для всех пользователей:", parse_mode=ParseMode.HTML)
    await state.set_state(Notify.waiting_for_notification)
    await callback_query.answer()


async def process_notification_text(message: types.Message, state: FSMContext):
    """Обработка текста уведомления"""
    try:
        from aiogram import Bot
        from config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        
        notification_service = NotificationService(bot)
        result = await notification_service.send_to_all_users(message.text)
        
        if result['success']:
            await message.answer(
                f"✅ <b>Уведомление отправлено!</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"   • Отправлено: {result['sent_count']}\n"
                f"   • Ошибок: {result['failed_count']}\n"
                f"   • Всего пользователей: {result['total_count']}",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(f"❌ <b>Ошибка:</b> {result.get('error', 'Неизвестная ошибка')}", parse_mode=ParseMode.HTML)
        
        await log_admin_action(message.from_user.id, f"sent_notification_to_{result.get('sent_count', 0)}_users")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {e}")
        await message.answer("❌ Произошла ошибка при отправке уведомлений.")
    
    await state.clear()


def register_admin_handlers(dp: Dispatcher):
    """Регистрирует обработчики для администраторов"""
    
    # Админ панель
    dp.callback_query.register(
        admin_panel_callback,
        lambda c: c.data == "admin_panel"
    )
    
    # Управление пользователями
    dp.callback_query.register(
        view_users_callback,
        lambda c: c.data == "view_users"
    )
    
    dp.callback_query.register(
        view_requests_callback,
        lambda c: c.data == "view_requests"
    )
    
    dp.callback_query.register(
        assign_role_callback,
        lambda c: c.data == "assign_role"
    )
    
    # Одобрение/отклонение
    dp.callback_query.register(
        approve_user_callback,
        lambda c: c.data and c.data.startswith("approve_") and not c.data.startswith("approve_news_")
    )
    
    dp.callback_query.register(
        decline_user_callback,
        lambda c: c.data and c.data.startswith("decline_")
    )
    
    # Синхронизация
    dp.callback_query.register(
        sync_data_callback,
        lambda c: c.data == "sync_data"
    )
    
    dp.callback_query.register(
        sync_bitrix24_callback,
        lambda c: c.data == "sync_bitrix24"
    )
    
    # Уведомления
    dp.callback_query.register(
        send_notification_callback,
        lambda c: c.data == "send_notification"
    )
    
    dp.message.register(
        process_notification_text,
        Notify.waiting_for_notification
    ) 