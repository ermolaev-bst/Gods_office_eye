#!/usr/bin/env python3
"""
Telegram бот для офиса - модульная версия
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, time

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

# Импорты конфигурации
from config import BOT_TOKEN, ADMIN_ID, DB_PATH

# Импорты модулей
from handlers import register_all_handlers
from database import init_db
from services import NotificationService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Сервисы
notification_service = NotificationService(bot)


async def periodic_tasks():
    """Периодические задачи"""
    while True:
        try:
            current_time = datetime.now()
            
            # Уведомления о кофе в 10:00
            if current_time.time() >= time(10, 0) and current_time.time() < time(10, 30):
                await send_coffee_notifications()
            
            # Периодическая синхронизация канала в 17:00
            if current_time.time() >= time(17, 0) and current_time.time() < time(17, 30):
                await periodic_channel_sync()
            
            # Ожидание 30 минут до следующей проверки
            await asyncio.sleep(1800)  # 30 минут
            
        except Exception as e:
            logger.error(f"Ошибка в периодических задачах: {e}")
            await asyncio.sleep(300)  # 5 минут при ошибке


async def send_coffee_notifications():
    """Отправка уведомлений о кофе"""
    try:
        from database import get_coffee_notifications
        
        notifications = await get_coffee_notifications()
        
        for notification in notifications:
            user_id, fio, date = notification[3], notification[1], notification[2]
            
            success = await notification_service.send_coffee_reminder(user_id, fio, date)
            
            if success:
                # Отмечаем уведомление как отправленное
                from database import mark_coffee_notification_sent
                await mark_coffee_notification_sent(notification[0])
        
        if notifications:
            logger.info(f"📢 Отправлено {len(notifications)} уведомлений о кофе")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомлений о кофе: {e}")


async def periodic_channel_sync():
    """Периодическая синхронизация канала"""
    try:
        from services import sync_with_channel
        
        result = await sync_with_channel()
        
        if result.get('success'):
            logger.info("✅ Периодическая синхронизация канала выполнена")
        else:
            logger.error(f"❌ Ошибка периодической синхронизации канала: {result.get('error')}")
    
    except Exception as e:
        logger.error(f"Ошибка периодической синхронизации канала: {e}")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Запуск бота...")
    
    # Инициализация базы данных
    try:
        await init_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False
    
    # Регистрация обработчиков
    try:
        register_all_handlers(dp)
        logger.info("✅ Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации обработчиков: {e}")
        return False
    
    # Уведомление администратора о запуске
    try:
        await notification_service.send_admin_notification(
            ADMIN_ID,
            "Запуск бота",
            "🤖 Бот успешно запущен и готов к работе!"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление админу: {e}")
    
    logger.info("✅ Бот успешно запущен!")
    return True


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Остановка бота...")
    
    # Уведомление администратора об остановке
    try:
        await notification_service.send_admin_notification(
            ADMIN_ID,
            "Остановка бота",
            "🛑 Бот остановлен"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление об остановке: {e}")
    
    logger.info("✅ Бот остановлен")


async def main():
    """Главная функция"""
    try:
        # Запуск
        if not await on_startup():
            logger.error("❌ Ошибка запуска бота")
            return
        
        # Запуск периодических задач в фоне
        periodic_task = asyncio.create_task(periodic_tasks())
        
        # Запуск поллинга
        try:
            await dp.start_polling(bot)
        finally:
            periodic_task.cancel()
            try:
                await periodic_task
            except asyncio.CancelledError:
                pass
    
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    
    finally:
        await on_shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1) 