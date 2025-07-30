"""
Вспомогательные функции для бота
"""

import html
import re
from typing import Optional


def escape_html(text: str) -> str:
    """Экранирует HTML символы в тексте"""
    if not text:
        return ""
    return html.escape(str(text))


def format_user_info(user_id: int, username: str, fio: str, position: str, role: str = None) -> str:
    """Форматирует информацию о пользователе"""
    safe_fio = escape_html(fio) if fio else 'Не указано'
    safe_username = escape_html(username) if username else 'Нет'
    safe_position = escape_html(position) if position else 'Не указано'
    safe_role = escape_html(role) if role else 'user'
    
    text = f"👤 <b>{safe_fio}</b>\n"
    text += f"🆔 ID: <code>{user_id}</code>\n"
    text += f"📱 @{safe_username}\n"
    text += f"💼 {safe_position}\n"
    
    if role:
        text += f"👑 Роль: {safe_role}\n"
    
    return text


def validate_fio(fio: str) -> bool:
    """Проверяет корректность ФИО"""
    if not fio or len(fio.strip()) < 2:
        return False
    
    # Проверяем, что ФИО содержит только буквы, пробелы и дефисы
    pattern = r'^[а-яА-ЯёЁa-zA-Z\s\-\.]+$'
    return bool(re.match(pattern, fio.strip()))


def validate_phone(phone: str) -> bool:
    """Проверяет корректность номера телефона"""
    if not phone:
        return False
    
    # Убираем все символы кроме цифр и +
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Проверяем различные форматы телефонов
    patterns = [
        r'^\+7\d{10}$',  # +7XXXXXXXXXX
        r'^8\d{10}$',    # 8XXXXXXXXXX
        r'^7\d{10}$',    # 7XXXXXXXXXX
        r'^\d{3,4}$',    # Короткий номер XXX или XXXX
    ]
    
    return any(re.match(pattern, clean_phone) for pattern in patterns)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Обрезает текст до указанной длины"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_datetime(dt, format_str: str = "%d.%m.%Y %H:%M") -> str:
    """Форматирует дату и время"""
    if not dt:
        return "Не указано"
    
    try:
        return dt.strftime(format_str)
    except:
        return str(dt)


def clean_callback_data(data: str) -> str:
    """Очищает callback_data от недопустимых символов"""
    if not data:
        return ""
    
    # Telegram ограничивает callback_data до 64 байт
    data = data[:64]
    
    # Убираем недопустимые символы
    return re.sub(r'[^\w\-_]', '_', data)


def get_role_display_name(role: str) -> str:
    """Возвращает отображаемое имя роли"""
    role_names = {
        'admin': '👑 Администратор',
        'moderator': '🛡️ Модератор',
        'marketer': '📢 Маркетолог',
        'user': '👤 Пользователь'
    }
    return role_names.get(role, role) 