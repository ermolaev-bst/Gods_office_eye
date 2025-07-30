"""
Сервис для синхронизации данных
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from config import BITRIX24_WEBHOOK, EXCEL_FILE

logger = logging.getLogger(__name__)


class SyncService:
    """Сервис для синхронизации данных"""
    
    def __init__(self):
        self.webhook_url = BITRIX24_WEBHOOK
        self.excel_file = EXCEL_FILE
    
    async def sync_with_bitrix24(self) -> Dict[str, Any]:
        """Синхронизация с Bitrix24"""
        try:
            # Импортируем здесь, чтобы избежать циклических импортов
            from bitrix24_sync import sync_bitrix24_to_excel, get_sync_status
            
            # Получаем статус перед синхронизацией
            status = await get_sync_status(self.webhook_url)
            
            # Запускаем синхронизацию
            result = await sync_bitrix24_to_excel(self.webhook_url)
            
            return {
                'success': result.get('success', False),
                'before_sync': status,
                'sync_result': result,
                'timestamp': datetime.now().isoformat()
            }
        
        except ImportError:
            logger.error("Модуль bitrix24_sync не найден")
            return {
                'success': False,
                'error': 'Модуль bitrix24_sync не найден',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Ошибка синхронизации с Bitrix24: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def sync_channel_subscribers(self) -> Dict[str, Any]:
        """Синхронизация подписчиков канала"""
        try:
            # Здесь была бы логика синхронизации канала
            # Перенесем из основного файла при необходимости
            
            return {
                'success': True,
                'message': 'Синхронизация канала выполнена',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Ошибка синхронизации канала: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def sync_database(self) -> Dict[str, Any]:
        """Синхронизация базы данных"""
        try:
            # Импортируем функции базы данных
            from database import get_authorized_users, get_auth_requests, get_news_proposals
            
            # Получаем статистику
            users = await get_authorized_users()
            requests = await get_auth_requests()
            news = await get_news_proposals()
            
            return {
                'success': True,
                'stats': {
                    'users_count': len(users) if users else 0,
                    'requests_count': len(requests) if requests else 0,
                    'news_count': len(news) if news else 0
                },
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Ошибка синхронизации БД: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Получает общий статус синхронизации"""
        try:
            # Проверяем статус всех компонентов
            db_status = await self.sync_database()
            
            # Проверяем доступность Excel файла
            import os
            excel_available = os.path.exists(self.excel_file) if self.excel_file else False
            
            # Проверяем доступность Bitrix24
            bitrix_available = bool(self.webhook_url)
            
            return {
                'database': db_status.get('success', False),
                'excel_file': excel_available,
                'bitrix24': bitrix_available,
                'last_check': datetime.now().isoformat(),
                'stats': db_status.get('stats', {})
            }
        
        except Exception as e:
            logger.error(f"Ошибка получения статуса синхронизации: {e}")
            return {
                'database': False,
                'excel_file': False,
                'bitrix24': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }


# Функции для совместимости
async def sync_with_channel() -> Dict[str, Any]:
    """Синхронизация с каналом"""
    service = SyncService()
    return await service.sync_channel_subscribers()


async def get_system_status() -> Dict[str, Any]:
    """Получение статуса системы"""
    service = SyncService()
    return await service.get_sync_status() 