#!/usr/bin/env python3
"""
Скрипт для автоматического обновления дат в CHANGELOG.md
Использует системную дату для проставления актуальных дат
"""

import os
import re
from datetime import datetime
import argparse

def get_current_date():
    """Получает текущую дату в формате YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")

def update_changelog_date(changelog_path="CHANGELOG.md", version="1.0.0"):
    """
    Обновляет дату в CHANGELOG.md для указанной версии
    
    Args:
        changelog_path (str): Путь к файлу CHANGELOG.md
        version (str): Версия для обновления даты
    """
    
    if not os.path.exists(changelog_path):
        print(f"❌ Файл {changelog_path} не найден!")
        return False
    
    # Читаем содержимое файла
    with open(changelog_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    current_date = get_current_date()
    
    # Паттерн для поиска версии с датой
    pattern = rf'## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}'
    replacement = f'## [{version}] - {current_date}'
    
    # Проверяем, есть ли уже дата для этой версии
    if re.search(pattern, content):
        # Обновляем существующую дату
        new_content = re.sub(pattern, replacement, content)
        print(f"✅ Обновлена дата для версии {version}: {current_date}")
    else:
        # Ищем версию без даты
        pattern_no_date = rf'## \[{re.escape(version)}\]'
        if re.search(pattern_no_date, content):
            # Добавляем дату к версии без даты
            new_content = re.sub(pattern_no_date, replacement, content)
            print(f"✅ Добавлена дата для версии {version}: {current_date}")
        else:
            print(f"❌ Версия {version} не найдена в CHANGELOG.md")
            return False
    
    # Записываем обновленное содержимое
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def create_release_entry(changelog_path="CHANGELOG.md", version=None):
    """
    Создает новую запись релиза в CHANGELOG.md
    
    Args:
        changelog_path (str): Путь к файлу CHANGELOG.md
        version (str): Новая версия для создания
    """
    
    if not os.path.exists(changelog_path):
        print(f"❌ Файл {changelog_path} не найден!")
        return False
    
    if not version:
        print("❌ Не указана версия для нового релиза!")
        return False
    
    current_date = get_current_date()
    
    # Читаем содержимое файла
    with open(changelog_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем новую запись релиза
    new_release = f"""## [{version}] - {current_date}

### Добавлено
- 

### Изменено
- 

### Исправлено
- 

"""
    
    # Вставляем новую версию после [Unreleased]
    pattern = r'(## \[Unreleased\].*?)(\n## \[)'
    replacement = rf'\1\n\n{new_release}\2'
    
    if re.search(pattern, content, re.DOTALL):
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        print(f"✅ Создана новая запись релиза для версии {version}")
    else:
        print("❌ Не удалось найти секцию [Unreleased]")
        return False
    
    # Записываем обновленное содержимое
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description='Обновление дат в CHANGELOG.md')
    parser.add_argument('--file', '-f', default='CHANGELOG.md', 
                       help='Путь к файлу CHANGELOG.md (по умолчанию: CHANGELOG.md)')
    parser.add_argument('--version', '-v', default='1.0.0',
                       help='Версия для обновления (по умолчанию: 1.0.0)')
    parser.add_argument('--new-release', '-n', 
                       help='Создать новую запись релиза с указанной версией')
    
    args = parser.parse_args()
    
    print(f"📅 Текущая дата: {get_current_date()}")
    
    if args.new_release:
        # Создаем новую запись релиза
        success = create_release_entry(args.file, args.new_release)
    else:
        # Обновляем дату для существующей версии
        success = update_changelog_date(args.file, args.version)
    
    if success:
        print(f"✅ CHANGELOG.md успешно обновлен!")
    else:
        print("❌ Ошибка при обновлении CHANGELOG.md")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 