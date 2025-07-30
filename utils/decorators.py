"""
Декораторы для проверки прав доступа
"""

from functools import wraps
from aiogram import types
from config import ADMIN_ID, MODERATOR_ID, MARKETER_ID


def admin_required(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(message_or_query, *args, **kwargs):
        user_id = None
        
        if isinstance(message_or_query, types.Message):
            user_id = message_or_query.from_user.id
        elif isinstance(message_or_query, types.CallbackQuery):
            user_id = message_or_query.from_user.id
        
        if user_id != ADMIN_ID:
            if isinstance(message_or_query, types.Message):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.")
            elif isinstance(message_or_query, types.CallbackQuery):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper


def moderator_required(func):
    """Декоратор для проверки прав модератора или администратора"""
    @wraps(func)
    async def wrapper(message_or_query, *args, **kwargs):
        user_id = None
        
        if isinstance(message_or_query, types.Message):
            user_id = message_or_query.from_user.id
        elif isinstance(message_or_query, types.CallbackQuery):
            user_id = message_or_query.from_user.id
        
        if user_id not in [ADMIN_ID, MODERATOR_ID]:
            if isinstance(message_or_query, types.Message):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.")
            elif isinstance(message_or_query, types.CallbackQuery):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper


def marketer_required(func):
    """Декоратор для проверки прав маркетолога, модератора или администратора"""
    @wraps(func)
    async def wrapper(message_or_query, *args, **kwargs):
        user_id = None
        
        if isinstance(message_or_query, types.Message):
            user_id = message_or_query.from_user.id
        elif isinstance(message_or_query, types.CallbackQuery):
            user_id = message_or_query.from_user.id
        
        if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
            if isinstance(message_or_query, types.Message):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.")
            elif isinstance(message_or_query, types.CallbackQuery):
                await message_or_query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper


def authorized_required(func):
    """Декоратор для проверки авторизации пользователя"""
    @wraps(func)
    async def wrapper(message_or_query, *args, **kwargs):
        from database import is_user_authorized
        
        user_id = None
        
        if isinstance(message_or_query, types.Message):
            user_id = message_or_query.from_user.id
        elif isinstance(message_or_query, types.CallbackQuery):
            user_id = message_or_query.from_user.id
        
        # Проверяем авторизацию
        if not await is_user_authorized(user_id):
            if isinstance(message_or_query, types.Message):
                await message_or_query.answer("❌ Вы не авторизованы. Отправьте заявку на авторизацию.")
            elif isinstance(message_or_query, types.CallbackQuery):
                await message_or_query.answer("❌ Вы не авторизованы.", show_alert=True)
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper 