"""
Модуль обработчиков для Telegram бота
"""

from .admin_handlers import register_admin_handlers
from .user_handlers import register_user_handlers  
from .moderator_handlers import register_moderator_handlers
from .common_handlers import register_common_handlers

__all__ = [
    'register_admin_handlers',
    'register_user_handlers',
    'register_moderator_handlers', 
    'register_common_handlers'
]


def register_all_handlers(dp):
    """Регистрирует все обработчики"""
    register_common_handlers(dp)
    register_user_handlers(dp)
    register_moderator_handlers(dp)
    register_admin_handlers(dp) 