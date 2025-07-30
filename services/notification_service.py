"""
Сервис для отправки уведомлений
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from aiogram import Bot
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_to_user(self, user_id: int, message: str, parse_mode: ParseMode = ParseMode.HTML) -> bool:
        """Отправляет сообщение конкретному пользователю"""
        try:
            await self.bot.send_message(user_id, message, parse_mode=parse_mode)
            logger.info(f"Уведомление отправлено пользователю {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            return False
    
    async def send_to_all_users(self, message: str, parse_mode: ParseMode = ParseMode.HTML) -> Dict[str, Any]:
        """Отправляет сообщение всем авторизованным пользователям"""
        try:
            from database import get_authorized_users
            
            users = await get_authorized_users()
            if not users:
                return {
                    'success': False,
                    'error': 'Нет авторизованных пользователей',
                    'sent_count': 0,
                    'total_count': 0
                }
            
            sent_count = 0
            failed_users = []
            
            for user in users:
                user_id = user[0]  # Первый элемент - ID пользователя
                
                try:
                    await self.bot.send_message(user_id, message, parse_mode=parse_mode)
                    sent_count += 1
                    logger.debug(f"Уведомление отправлено пользователю {user_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                    failed_users.append(user_id)
            
            return {
                'success': True,
                'sent_count': sent_count,
                'failed_count': len(failed_users),
                'total_count': len(users),
                'failed_users': failed_users,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Ошибка массовой отправки уведомлений: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0,
                'total_count': 0
            }
    
    async def send_to_channel(self, channel_id: int, message: str, parse_mode: ParseMode = ParseMode.HTML) -> bool:
        """Отправляет сообщение в канал"""
        try:
            await self.bot.send_message(channel_id, message, parse_mode=parse_mode)
            logger.info(f"Сообщение отправлено в канал {channel_id}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка отправки в канал {channel_id}: {e}")
            return False
    
    async def send_admin_notification(self, admin_id: int, title: str, message: str, 
                                    parse_mode: ParseMode = ParseMode.HTML) -> bool:
        """Отправляет уведомление администратору"""
        try:
            formatted_message = f"🔔 <b>{title}</b>\n\n{message}\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            return await self.send_to_user(admin_id, formatted_message, parse_mode)
        
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
            return False
    
    async def send_role_based_notification(self, message: str, roles: List[str], 
                                         parse_mode: ParseMode = ParseMode.HTML) -> Dict[str, Any]:
        """Отправляет уведомление пользователям с определенными ролями"""
        try:
            from database import get_users_by_roles
            
            users = await get_users_by_roles(roles)
            if not users:
                return {
                    'success': False,
                    'error': f'Нет пользователей с ролями: {", ".join(roles)}',
                    'sent_count': 0,
                    'total_count': 0
                }
            
            sent_count = 0
            failed_users = []
            
            for user in users:
                user_id = user[0]  # Первый элемент - ID пользователя
                
                try:
                    await self.bot.send_message(user_id, message, parse_mode=parse_mode)
                    sent_count += 1
                
                except Exception as e:
                    logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
                    failed_users.append(user_id)
            
            return {
                'success': True,
                'sent_count': sent_count,
                'failed_count': len(failed_users),
                'total_count': len(users),
                'failed_users': failed_users,
                'roles': roles,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Ошибка отправки по ролям: {e}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0,
                'total_count': 0
            }
    
    async def send_coffee_reminder(self, user_id: int, fio: str, date: str) -> bool:
        """Отправляет напоминание о кофе"""
        try:
            message = f"☕ <b>Напоминание о кофе</b>\n\n"
            message += f"👤 <b>Ответственный:</b> {fio}\n"
            message += f"📅 <b>Дата:</b> {date}\n\n"
            message += f"Не забудьте приготовить кофе для коллег! ☕"
            
            return await self.send_to_user(user_id, message)
        
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о кофе: {e}")
            return False


# Функции для совместимости
async def send_notification_to_all(bot: Bot, message: str) -> Dict[str, Any]:
    """Отправка уведомления всем пользователям"""
    service = NotificationService(bot)
    return await service.send_to_all_users(message)


async def send_admin_alert(bot: Bot, admin_id: int, title: str, message: str) -> bool:
    """Отправка уведомления администратору"""
    service = NotificationService(bot)
    return await service.send_admin_notification(admin_id, title, message) 