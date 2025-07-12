"""
Скрипт для запуска синхронизации сотрудников Bitrix24 с Excel файлом
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Добавляем текущую директорию в путь для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bitrix24_sync import sync_bitrix24_to_excel, get_sync_status
from config import EXCEL_FILE, BITRIX24_WEBHOOK

# Загружаем переменные окружения
load_dotenv()

async def main():
    """Основная функция синхронизации"""
    print("=== Синхронизация сотрудников Bitrix24 ===")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Проверяем наличие webhook URL
    if not BITRIX24_WEBHOOK:
        print("❌ BITRIX24_WEBHOOK не найден в переменных окружения!")
        print("Добавьте BITRIX24_WEBHOOK в файл .env")
        return
    
    print(f"🔗 Webhook URL: {BITRIX24_WEBHOOK}")
    print(f"📁 Excel файл: {EXCEL_FILE}")
    print()
    
    # Проверяем статус перед синхронизацией
    print("📊 Проверка текущего статуса...")
    try:
        status = await get_sync_status(BITRIX24_WEBHOOK)
        print(f"   - Записей в Excel: {status.get('excel_records', 0)}")
        print(f"   - Сотрудников в Bitrix24: {status.get('bitrix_users', 0)}")
        print()
    except Exception as e:
        print(f"⚠️ Ошибка получения статуса: {e}")
        print()
    
    # Запускаем синхронизацию
    print("🔄 Запуск синхронизации...")
    try:
        result = await sync_bitrix24_to_excel(BITRIX24_WEBHOOK)
        
        if result['success']:
            details = result['details']
            print("✅ Синхронизация завершена успешно!")
            print()
            print("📈 Результаты:")
            print(f"   - Записей до синхронизации: {details.get('initial_count', 0)}")
            print(f"   - Записей после синхронизации: {details.get('final_count', 0)}")
            print(f"   - Обновлено записей: {details.get('updated_count', 0)}")
            print(f"   - Добавлено новых записей: {details.get('added_count', 0)}")
            print(f"   - Пропущено записей: {details.get('skipped_count', 0)}")
            print(f"   - Сотрудников в Bitrix24: {details.get('bitrix_users', 0)}")
        else:
            print(f"❌ Ошибка синхронизации: {result.get('error', 'Неизвестная ошибка')}")
    
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    
    print()
    print(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main()) 