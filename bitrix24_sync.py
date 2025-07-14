"""
Модуль для синхронизации сотрудников из Bitrix24 в Excel файл
"""

import asyncio
import aiohttp
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import os

logger = logging.getLogger(__name__)

class Bitrix24Client:
    """Клиент для работы с API Bitrix24"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.base_url = webhook_url.rstrip('/')
    
    async def _make_request(self, method: str, params: Dict = None) -> Dict:
        """Выполняет запрос к API Bitrix24"""
        if params is None:
            params = {}
        
        url = f"{self.base_url}/{method}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'result' in data:
                            return data['result']
                        elif 'error' in data:
                            logger.error(f"Bitrix24 API error: {data['error']}")
                            return {}
                        else:
                            return data
                    else:
                        logger.error(f"HTTP error {response.status}: {await response.text()}")
                        return {}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {}
    
    async def get_users(self) -> List[Dict]:
        """Получает список всех пользователей из Bitrix24"""
        users = []
        start = 0
        
        while True:
            params = {
                'start': start,
                'ACTIVE': True
            }
            
            result = await self._make_request('user.get', params)
            
            if not result:
                break
            
            users.extend(result)
            
            # Если получили меньше 50 записей, значит это последняя страница
            if len(result) < 50:
                break
            
            start += 50
        
        return users
    
    async def get_departments(self) -> List[Dict]:
        """Получает список всех отделов из Bitrix24"""
        result = await self._make_request('department.get')
        return result if result else []

async def sync_bitrix24_to_excel(webhook_url: str, excel_file: str = None) -> Dict[str, Any]:
    """
    Синхронизирует сотрудников из Bitrix24 в Excel файл
    
    Args:
        webhook_url: URL webhook'а Bitrix24
        excel_file: Путь к Excel файлу (если None, берется из config)
    
    Returns:
        Dict с результатами синхронизации
    """
    if excel_file is None:
        from config import EXCEL_FILE
        excel_file = EXCEL_FILE
    
    logger.info(f"Начинаем синхронизацию Bitrix24 -> Excel: {excel_file}")
    
    try:
        # Создаем клиент Bitrix24
        client = Bitrix24Client(webhook_url)
        
        # Получаем данные из Bitrix24
        logger.info("Получаем пользователей из Bitrix24...")
        users = await client.get_users()
        
        logger.info("Получаем отделы из Bitrix24...")
        departments = await client.get_departments()
        
        # Создаем словарь отделов для быстрого поиска
        dept_dict = {dept['ID']: dept['NAME'] for dept in departments}
        
        # Подготавливаем данные для Excel
        excel_data = []
        
        for user in users:
            # Получаем отдел пользователя
            department_name = ""
            if 'UF_DEPARTMENT' in user and user['UF_DEPARTMENT']:
                dept_ids = user['UF_DEPARTMENT']
                if isinstance(dept_ids, list):
                    dept_names = [dept_dict.get(str(dept_id), "") for dept_id in dept_ids]
                    department_name = ", ".join(filter(None, dept_names))
                else:
                    department_name = dept_dict.get(str(dept_ids), "")
            
            # Формируем ФИО
            fio_parts = []
            if user.get('LAST_NAME'):
                fio_parts.append(user['LAST_NAME'])
            if user.get('NAME'):
                fio_parts.append(user['NAME'])
            if user.get('SECOND_NAME'):
                fio_parts.append(user['SECOND_NAME'])
            
            full_name = " ".join(fio_parts) if fio_parts else user.get('LOGIN', 'Неизвестно')
            
            # Добавляем запись
            excel_data.append({
                'ФИО': full_name,
                'Должность': user.get('WORK_POSITION', ''),
                'Отдел': department_name,
                'Фото': None,  # Фото не синхронизируем из Bitrix24
                'Email': user.get('EMAIL', ''),
                'Телефон': user.get('WORK_PHONE', ''),
                'ID_Bitrix24': user.get('ID', ''),
                'Дата_синхронизации': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Создаем DataFrame
        df_new = pd.DataFrame(excel_data)
        
        # Читаем существующий файл для сравнения
        initial_count = 0
        updated_count = 0
        added_count = 0
        skipped_count = 0
        
        if os.path.exists(excel_file):
            try:
                df_old = pd.read_excel(excel_file)
                initial_count = len(df_old)
                
                # Сравниваем записи по ФИО
                for _, new_row in df_new.iterrows():
                    fio = new_row['ФИО']
                    old_row = df_old[df_old['ФИО'] == fio]
                    
                    if len(old_row) > 0:
                        # Запись существует - проверяем изменения
                        old_data = old_row.iloc[0]
                        if (old_data['Должность'] != new_row['Должность'] or 
                            old_data['Отдел'] != new_row['Отдел']):
                            updated_count += 1
                        else:
                            skipped_count += 1
                    else:
                        # Новая запись
                        added_count += 1
                        
            except Exception as e:
                logger.warning(f"Не удалось прочитать существующий файл: {e}")
                added_count = len(df_new)
        else:
            added_count = len(df_new)
        
        # Сохраняем новый файл
        df_new.to_excel(excel_file, index=False)
        final_count = len(df_new)
        
        logger.info(f"Синхронизация завершена. Записей: {final_count}")
        
        return {
            'success': True,
            'details': {
                'initial_count': initial_count,
                'final_count': final_count,
                'updated_count': updated_count,
                'added_count': added_count,
                'skipped_count': skipped_count,
                'bitrix_users': len(users)
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка синхронизации: {e}")
        return {
            'success': False,
            'error': str(e)
        }

async def get_sync_status(webhook_url: str, excel_file: str = None) -> Dict[str, Any]:
    """
    Получает статус синхронизации
    
    Args:
        webhook_url: URL webhook'а Bitrix24
        excel_file: Путь к Excel файлу
    
    Returns:
        Dict с информацией о статусе
    """
    if excel_file is None:
        from config import EXCEL_FILE
        excel_file = EXCEL_FILE
    
    try:
        # Получаем количество пользователей в Bitrix24
        client = Bitrix24Client(webhook_url)
        users = await client.get_users()
        
        # Получаем количество записей в Excel
        excel_records = 0
        if os.path.exists(excel_file):
            try:
                df = pd.read_excel(excel_file)
                excel_records = len(df)
            except Exception as e:
                logger.warning(f"Не удалось прочитать Excel файл: {e}")
        
        return {
            'excel_records': excel_records,
            'bitrix_users': len(users),
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        return {
            'excel_records': 0,
            'bitrix_users': 0,
            'error': str(e)
        }

# Функции для совместимости с существующим кодом
async def sync_bitrix24_to_excel_contacts(webhook_url: str, excel_file: str = None) -> Dict[str, Any]:
    """Алиас для совместимости"""
    return await sync_bitrix24_to_excel(webhook_url, excel_file)

def sync_bitrix24_to_excel_sync(webhook_url: str, excel_file: str = None) -> Dict[str, Any]:
    """Синхронная версия функции для совместимости"""
    return asyncio.run(sync_bitrix24_to_excel(webhook_url, excel_file))

def get_sync_status_sync(webhook_url: str, excel_file: str = None) -> Dict[str, Any]:
    """Синхронная версия функции получения статуса"""
    return asyncio.run(get_sync_status(webhook_url, excel_file)) 