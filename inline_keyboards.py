from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Tuple, Optional

class BeautifulInlineKeyboards:
    """Класс для создания красивых инлайн клавиатур"""
    
    @staticmethod
    def create_approval_keyboard(user_id: int, show_details: bool = False) -> InlineKeyboardMarkup:
        """Создает красивую клавиатуру для одобрения/отклонения заявок"""
        builder = InlineKeyboardBuilder()
        
        # Основные кнопки
        builder.add(InlineKeyboardButton(
            text="✅ Одобрить", 
            callback_data=f"approve_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отклонить", 
            callback_data=f"decline_{user_id}"
        ))
        
        # Дополнительные кнопки
        if show_details:
            builder.add(InlineKeyboardButton(
                text="👁️ Подробнее", 
                callback_data=f"details_{user_id}"
            ))
        
        builder.add(InlineKeyboardButton(
            text="📝 Добавить комментарий", 
            callback_data=f"comment_{user_id}"
        ))
        
        # Настройка расположения кнопок
        if show_details:
            builder.adjust(2, 1, 1)  # 2 кнопки в первом ряду, по 1 в остальных
        else:
            builder.adjust(2, 1)  # 2 кнопки в первом ряду, 1 во втором
        
        return builder.as_markup()
    
    @staticmethod
    def create_news_approval_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
        """Создает красивую клавиатуру для одобрения/отклонения новостей"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Проверяем, что proposal_id корректный
        if not isinstance(proposal_id, int) or proposal_id <= 0:
            logger.error(f"KEYBOARD: Invalid proposal_id={proposal_id} (type={type(proposal_id)})")
            raise ValueError(f"Invalid proposal_id: {proposal_id}")
        
        logger.debug(f"KEYBOARD: Creating approval keyboard for proposal_id={proposal_id}")
        
        builder = InlineKeyboardBuilder()
        
        # Основные кнопки
        approve_callback = f"approve_news_{proposal_id}"
        reject_callback = f"reject_news_{proposal_id}"
        edit_callback = f"edit_news_{proposal_id}"
        comment_callback = f"comment_news_{proposal_id}"
        
        logger.debug(f"KEYBOARD: approve_callback='{approve_callback}' (length={len(approve_callback)})")
        logger.debug(f"KEYBOARD: reject_callback='{reject_callback}' (length={len(reject_callback)})")
        logger.debug(f"KEYBOARD: edit_callback='{edit_callback}' (length={len(edit_callback)})")
        logger.debug(f"KEYBOARD: comment_callback='{comment_callback}' (length={len(comment_callback)})")
        
        builder.add(InlineKeyboardButton(
            text="✅ Одобрить и опубликовать", 
            callback_data=approve_callback
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отклонить", 
            callback_data=reject_callback
        ))
        
        # Дополнительные кнопки
        builder.add(InlineKeyboardButton(
            text="✏️ Редактировать", 
            callback_data=edit_callback
        ))
        builder.add(InlineKeyboardButton(
            text="📝 Добавить комментарий", 
            callback_data=comment_callback
        ))
        
        # Настройка расположения кнопок
        builder.adjust(1, 1, 2)  # По 1 кнопке в первых двух рядах, 2 в последнем
        
        keyboard = builder.as_markup()
        logger.debug(f"KEYBOARD: Created keyboard with {len(keyboard.inline_keyboard)} rows")
        
        return keyboard
    
    @staticmethod
    def create_main_menu_keyboard() -> InlineKeyboardMarkup:
        """Создает красивую главную инлайн клавиатуру"""
        builder = InlineKeyboardBuilder()
        
        # Основные функции пользователя
        builder.add(InlineKeyboardButton(
            text="🔍 Поиск сотрудников", 
            callback_data="search_employees"
        ))
        
        # Новости и уведомления
        builder.add(InlineKeyboardButton(
            text="📝 Предложить новость", 
            callback_data="propose_news"
        ))
        builder.add(InlineKeyboardButton(
            text="📅 График кофе", 
            callback_data="coffee_schedule"
        ))
        
        # Административные функции
        builder.add(InlineKeyboardButton(
            text="⚙️ Админ панель", 
            callback_data="admin_panel"
        ))
        builder.add(InlineKeyboardButton(
            text="🛡️ Модератор панель", 
            callback_data="moderator_panel"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2, 2)  # По 2 кнопки в каждом ряду
        
        return builder.as_markup()
    
    @staticmethod
    def create_user_functions_keyboard() -> InlineKeyboardMarkup:
        """Создает клавиатуру с функциями пользователя"""
        builder = InlineKeyboardBuilder()
        
        # Основные функции
        builder.add(InlineKeyboardButton(
            text="🔍 Поиск сотрудников", 
            callback_data="search_employees"
        ))
        builder.add(InlineKeyboardButton(
            text="📥 Скачать контакты", 
            callback_data="download_contacts"
        ))
        
        # Новости и уведомления
        builder.add(InlineKeyboardButton(
            text="📝 Предложить новость", 
            callback_data="propose_news"
        ))
        builder.add(InlineKeyboardButton(
            text="📅 График кофе", 
            callback_data="coffee_schedule"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2)  # По 2 кнопки в каждом ряду
        
        return builder.as_markup()
    
    @staticmethod
    def create_admin_panel_keyboard() -> InlineKeyboardMarkup:
        """Создает красивую админ панель с уникальными функциями администратора"""
        builder = InlineKeyboardBuilder()
        
        # --- Админские функции (уникальные) ---
        builder.add(InlineKeyboardButton(text="📋 Просмотр заявок", callback_data="view_requests"))
        builder.add(InlineKeyboardButton(text="👥 Пользователи", callback_data="view_users"))
        builder.add(InlineKeyboardButton(text="👑 Назначить роль", callback_data="assign_role"))
        builder.add(InlineKeyboardButton(text="❌ Удалить пользователя", callback_data="remove_user"))
        builder.add(InlineKeyboardButton(text="🔔 Отправить уведомление", callback_data="send_notification"))
        

        
        # --- Синхронизация ---
        builder.add(InlineKeyboardButton(text="🔄 Синхронизация", callback_data="sync_data"))
        builder.add(InlineKeyboardButton(text="📺 Синхронизация канала", callback_data="sync_channel"))
        builder.add(InlineKeyboardButton(text="🔗 Пригласительная ссылка", callback_data="get_invite_link"))
        
        # Настройка сетки: 3 кнопки в ряд
        builder.adjust(3)
        
        return builder.as_markup()
    
    @staticmethod
    def create_moderator_panel_keyboard() -> InlineKeyboardMarkup:
        """Создает клавиатуру для модераторов с уникальными функциями"""
        builder = InlineKeyboardBuilder()
        
        # Функции пользователя
        builder.add(InlineKeyboardButton(
            text="🔍 Поиск сотрудников", 
            callback_data="search_employees"
        ))
        
        # Уникальные функции модератора
        builder.add(InlineKeyboardButton(
            text="📅 График на месяц", 
            callback_data="schedule_month"
        ))
        builder.add(InlineKeyboardButton(
            text="📅 График кофе", 
            callback_data="coffee_schedule"
        ))
        
        # Дополнительные функции
        builder.add(InlineKeyboardButton(
            text="📝 Предложить новость", 
            callback_data="propose_news"
        ))
        builder.add(InlineKeyboardButton(
            text="🔔 Уведомления", 
            callback_data="send_notification"
        ))
        
        # Назад
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data="back_to_main"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2, 2, 1)  # По 2 кнопки в каждом ряду, кроме последнего
        
        return builder.as_markup()
    
    @staticmethod
    def create_search_keyboard() -> InlineKeyboardMarkup:
        """Создает клавиатуру для поиска"""
        builder = InlineKeyboardBuilder()
        
        # Типы поиска
        builder.add(InlineKeyboardButton(
            text="👤 Поиск по ФИО", 
            callback_data="search_by_fio"
        ))
        builder.add(InlineKeyboardButton(
            text="💼 Поиск по должности", 
            callback_data="search_by_position"
        ))
        
        builder.add(InlineKeyboardButton(
            text="🏢 Поиск по отделу", 
            callback_data="search_by_department"
        ))
        builder.add(InlineKeyboardButton(
            text="📞 Поиск по телефону", 
            callback_data="search_by_phone"
        ))
        
        # Назад
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data="back_to_main"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2, 1)  # По 2 кнопки в первых двух рядах, 1 в последнем
        
        return builder.as_markup()
    

    
    @staticmethod
    def create_marketer_keyboard() -> InlineKeyboardMarkup:
        """Создает клавиатуру для маркетологов с функциями управления новостями"""
        builder = InlineKeyboardBuilder()
        
        # Управление новостями
        builder.add(InlineKeyboardButton(
            text="📢 Опубликовать новость", 
            callback_data="publish_news"
        ))
        builder.add(InlineKeyboardButton(
            text="📝 Создать новость", 
            callback_data="create_news"
        ))
        
        # Просмотр и модерация
        builder.add(InlineKeyboardButton(
            text="📋 Предложения новостей", 
            callback_data="review_news_proposals"
        ))
        builder.add(InlineKeyboardButton(
            text="📊 Статистика публикаций", 
            callback_data="publication_stats"
        ))
        
        # Планирование
        builder.add(InlineKeyboardButton(
            text="📅 Планировщик", 
            callback_data="content_scheduler"
        ))
        builder.add(InlineKeyboardButton(
            text="📊 Общая статистика", 
            callback_data="statistics"
        ))
        
        # Назад
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data="back_to_main"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2, 2, 1)  # По 2 кнопки в первых трех рядах, 1 в последнем
        
        return builder.as_markup()
    
    @staticmethod
    def create_pagination_keyboard(current_page: int, total_pages: int, 
                                 callback_prefix: str, extra_buttons: List[Tuple[str, str]] = None) -> InlineKeyboardMarkup:
        """Создает клавиатуру с пагинацией"""
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации
        if current_page > 1:
            builder.add(InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"{callback_prefix}_page_{current_page - 1}"
            ))
        
        builder.add(InlineKeyboardButton(
            text=f"📄 {current_page}/{total_pages}", 
            callback_data="current_page"
        ))
        
        if current_page < total_pages:
            builder.add(InlineKeyboardButton(
                text="Вперед ➡️", 
                callback_data=f"{callback_prefix}_page_{current_page + 1}"
            ))
        
        # Дополнительные кнопки
        if extra_buttons:
            for text, callback_data in extra_buttons:
                builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
        
        # Настройка расположения кнопок
        if extra_buttons:
            builder.adjust(3, len(extra_buttons))  # 3 кнопки в первом ряду, остальные во втором
        else:
            builder.adjust(3)  # Все 3 кнопки в одном ряду
        
        return builder.as_markup()
    
    @staticmethod
    def create_confirmation_keyboard(action: str, item_id: int, 
                                   confirm_text: str = "✅ Подтвердить",
                                   cancel_text: str = "❌ Отмена") -> InlineKeyboardMarkup:
        """Создает клавиатуру подтверждения действия"""
        builder = InlineKeyboardBuilder()
        
        builder.add(InlineKeyboardButton(
            text=confirm_text, 
            callback_data=f"confirm_{action}_{item_id}"
        ))
        builder.add(InlineKeyboardButton(
            text=cancel_text, 
            callback_data=f"cancel_{action}_{item_id}"
        ))
        
        builder.adjust(2)  # 2 кнопки в одном ряду
        
        return builder.as_markup()
    
    @staticmethod
    def create_role_selection_keyboard(user_id: int) -> InlineKeyboardMarkup:
        """Создает клавиатуру для выбора роли"""
        builder = InlineKeyboardBuilder()
        
        roles = [
            ("👑 Администратор", "admin"),
            ("🛡️ Модератор", "moderator"),
            ("📢 Маркетолог", "marketer"),
            ("👤 Пользователь", "user")
        ]
        
        for role_name, role_value in roles:
            builder.add(InlineKeyboardButton(
                text=role_name, 
                callback_data=f"assign_role_{user_id}_{role_value}"
            ))
        
        builder.add(InlineKeyboardButton(
            text="❌ Отмена", 
            callback_data=f"cancel_role_{user_id}"
        ))
        
        builder.adjust(2, 2, 1)  # По 2 кнопки в первых двух рядах, 1 в последнем
        
        return builder.as_markup()
    
    @staticmethod
    def create_quick_actions_keyboard() -> InlineKeyboardMarkup:
        """Создает клавиатуру быстрых действий"""
        builder = InlineKeyboardBuilder()
        
        # Быстрые действия
        builder.add(InlineKeyboardButton(
            text="📞 Позвонить", 
            callback_data="quick_call"
        ))
        builder.add(InlineKeyboardButton(
            text="✉️ Написать", 
            callback_data="quick_message"
        ))
        
        builder.add(InlineKeyboardButton(
            text="📍 Локация", 
            callback_data="quick_location"
        ))
        builder.add(InlineKeyboardButton(
            text="📋 Детали", 
            callback_data="quick_details"
        ))
        
        # Настройка расположения кнопок
        builder.adjust(2, 2)  # По 2 кнопки в каждом ряду
        
        return builder.as_markup()
    
    @staticmethod
    def create_news_photos_keyboard() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✅ Готово", callback_data="news_photos_done"))
        return builder.as_markup() 