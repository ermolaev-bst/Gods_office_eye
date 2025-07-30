"""
Обработчики для модераторов
"""

import logging
from datetime import datetime
from aiogram import types, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import ADMIN_ID, MODERATOR_ID, MARKETER_ID, CHANNEL_CHAT_ID
from database import *
from keyboards import *
from states import Moderator, ScheduleMonth
from utils import escape_html

logger = logging.getLogger(__name__)


# ============= ПАНЕЛИ МОДЕРАТОРА И МАРКЕТОЛОГА =============

async def moderator_panel_callback(callback_query: types.CallbackQuery):
    """Обработчик панели модератора"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID]:
        await callback_query.answer("❌ У вас нет прав для доступа к панели модератора.", show_alert=True)
        return
    
    keyboard = create_moderator_panel_keyboard()
    await callback_query.message.edit_text(
        "🛡️ <b>Панель модератора</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()


async def marketer_panel_callback(callback_query: types.CallbackQuery):
    """Обработчик панели маркетолога"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
        await callback_query.answer("❌ У вас нет прав для доступа к панели маркетолога.", show_alert=True)
        return
    
    keyboard = create_marketer_keyboard()
    await callback_query.message.edit_text(
        "📢 <b>Панель маркетолога</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()


# ============= УПРАВЛЕНИЕ НОВОСТЯМИ =============

async def publish_news_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик публикации новости"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
        await callback_query.answer("❌ У вас нет прав для публикации новостей.", show_alert=True)
        return
    
    await callback_query.message.answer(
        "📢 <b>Публикация новости</b>\n\n"
        "Введите текст новости для публикации в канале:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Moderator.waiting_for_news)
    await callback_query.answer()


async def process_moderator_news(message: types.Message, state: FSMContext):
    """Обработка публикации новости модератором"""
    try:
        # Публикуем новость в канал
        from aiogram import Bot
        from config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        
        await bot.send_message(
            CHANNEL_CHAT_ID, 
            f"📢 <b>Новость от модератора:</b>\n\n{message.text}", 
            parse_mode=ParseMode.HTML
        )
        
        await message.answer("✅ Новость опубликована в канале!")
        
        # Логируем действие
        await log_admin_action(message.from_user.id, f"published_news")
        
    except Exception as e:
        logger.error(f"Ошибка при публикации новости: {e}")
        await message.answer("❌ Произошла ошибка при публикации новости.")
    
    await state.clear()
    
    # Возвращаемся в главное меню
    from handlers.common_handlers import send_main_menu
    await send_main_menu(message, user_id=message.from_user.id)


async def news_proposals_callback(callback_query: types.CallbackQuery):
    """Обработчик просмотра предложений новостей"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
        await callback_query.answer("❌ У вас нет прав для просмотра предложений.", show_alert=True)
        return
    
    try:
        proposals = await get_news_proposals()
        
        if not proposals:
            await callback_query.message.answer("📋 Нет предложений новостей.")
            await callback_query.answer()
            return
        
        # Показываем только первые 5 предложений
        text = "📋 <b>Предложения новостей:</b>\n\n"
        
        for i, proposal in enumerate(proposals[:5], 1):
            proposal_id, author, text_content, created_at, status = proposal
            
            safe_author = escape_html(author)
            safe_text = escape_html(text_content[:100])
            
            status_emoji = "⏳" if status == "pending" else "✅" if status == "approved" else "❌"
            
            text += f"<b>{i}. #{proposal_id}</b> {status_emoji}\n"
            text += f"👤 <b>Автор:</b> {safe_author}\n"
            text += f"📝 <b>Текст:</b> {safe_text}{'...' if len(text_content) > 100 else ''}\n"
            text += f"📅 <b>Дата:</b> {created_at}\n"
            text += f"📊 <b>Статус:</b> {status}\n\n"
        
        if len(proposals) > 5:
            text += f"... и ещё {len(proposals) - 5} предложений"
        
        # Создаем клавиатуру с предложениями для модерации
        keyboard = create_news_proposals_keyboard(proposals[:5])
        
        await callback_query.message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при получении предложений новостей: {e}")
        await callback_query.answer("Произошла ошибка при загрузке предложений.", show_alert=True)


async def approve_news_callback(callback_query: types.CallbackQuery):
    """Обработчик одобрения предложения новости"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
        await callback_query.answer("❌ У вас нет прав для одобрения новостей.", show_alert=True)
        return
    
    try:
        # Парсим proposal_id из callback_data
        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("Ошибка: неверный формат callback_data", show_alert=True)
            return
        
        proposal_id = int(parts[2])
        
        # Получаем предложение
        proposal = await get_news_proposal_by_id(proposal_id)
        
        if not proposal:
            await callback_query.answer("❌ Предложение не найдено", show_alert=True)
            return
        
        proposal_id, author_id, text_content, author_name, created_at, status = proposal
        
        if status != "pending":
            await callback_query.answer(f"❌ Предложение уже обработано (статус: {status})", show_alert=True)
            return
        
        # Обновляем статус на "approved"
        await update_news_proposal_status(proposal_id, "approved")
        
        # Публикуем в канал
        try:
            from aiogram import Bot
            from config import BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)
            
            await bot.send_message(
                CHANNEL_CHAT_ID,
                f"📢 <b>Новость</b>\n\n{text_content}\n\n"
                f"<i>Предложено: {escape_html(author_name)}</i>",
                parse_mode=ParseMode.HTML
            )
            
            # Уведомляем автора
            try:
                await bot.send_message(
                    author_id,
                    f"✅ <b>Ваша новость одобрена и опубликована!</b>\n\n"
                    f"📝 <b>Текст:</b>\n{escape_html(text_content[:200])}{'...' if len(text_content) > 200 else ''}\n\n"
                    f"📅 <b>Опубликовано:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления автора {author_id}: {e}")
            
            await callback_query.answer("✅ Новость одобрена и опубликована!", show_alert=True)
            
            # Логируем действие
            await log_admin_action(user_id, f"approved_news_{proposal_id}")
            
        except Exception as e:
            logger.error(f"Ошибка публикации в канал: {e}")
            await callback_query.answer("❌ Ошибка при публикации в канал", show_alert=True)
    
    except Exception as e:
        logger.error(f"Ошибка одобрения новости: {e}")
        await callback_query.answer("❌ Ошибка при одобрении новости", show_alert=True)


async def reject_news_callback(callback_query: types.CallbackQuery):
    """Обработчик отклонения предложения новости"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID, MARKETER_ID]:
        await callback_query.answer("❌ У вас нет прав для отклонения новостей.", show_alert=True)
        return
    
    try:
        # Парсим proposal_id из callback_data
        parts = callback_query.data.split("_")
        if len(parts) < 3:
            await callback_query.answer("Ошибка: неверный формат callback_data", show_alert=True)
            return
        
        proposal_id = int(parts[2])
        
        # Получаем предложение
        proposal = await get_news_proposal_by_id(proposal_id)
        
        if not proposal:
            await callback_query.answer("❌ Предложение не найдено", show_alert=True)
            return
        
        proposal_id, author_id, text_content, author_name, created_at, status = proposal
        
        if status != "pending":
            await callback_query.answer(f"❌ Предложение уже обработано (статус: {status})", show_alert=True)
            return
        
        # Обновляем статус на "rejected"
        await update_news_proposal_status(proposal_id, "rejected")
        
        # Уведомляем автора
        try:
            from aiogram import Bot
            from config import BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)
            
            await bot.send_message(
                author_id,
                f"❌ <b>Ваше предложение новости отклонено</b>\n\n"
                f"📝 <b>Текст:</b>\n{escape_html(text_content[:200])}{'...' if len(text_content) > 200 else ''}\n\n"
                f"📅 <b>Отклонено:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Попробуйте предложить другую новость.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления автора {author_id}: {e}")
        
        await callback_query.answer("❌ Предложение отклонено", show_alert=True)
        
        # Логируем действие
        await log_admin_action(user_id, f"rejected_news_{proposal_id}")
    
    except Exception as e:
        logger.error(f"Ошибка отклонения новости: {e}")
        await callback_query.answer("❌ Ошибка при отклонении новости", show_alert=True)


# ============= ГРАФИК КОФЕ =============

async def coffee_schedule_callback(callback_query: types.CallbackQuery):
    """Обработчик просмотра графика кофе"""
    try:
        schedule = await get_coffee_schedule()
        
        if not schedule:
            await callback_query.message.answer("📅 График кофе пуст.")
            await callback_query.answer()
            return
        
        text = "☕ <b>График приготовления кофе:</b>\n\n"
        
        for i, entry in enumerate(schedule[:10], 1):  # Показываем первые 10
            entry_id, fio, date, user_id, created_by, created_at = entry
            
            safe_fio = escape_html(fio)
            
            text += f"<b>{i}.</b> 📅 <b>{date}</b>\n"
            text += f"👤 <b>Ответственный:</b> {safe_fio}\n"
            text += f"📅 <b>Добавлено:</b> {created_at}\n\n"
        
        if len(schedule) > 10:
            text += f"... и ещё {len(schedule) - 10} записей"
        
        # Создаем клавиатуру для управления графиком
        keyboard = create_schedule_keyboard([entry[2] for entry in schedule[:5]])
        
        await callback_query.message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при получении графика кофе: {e}")
        await callback_query.answer("Произошла ошибка при загрузке графика.", show_alert=True)


async def schedule_month_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработчик добавления графика на месяц"""
    user_id = callback_query.from_user.id
    
    if user_id not in [ADMIN_ID, MODERATOR_ID]:
        await callback_query.answer("❌ У вас нет прав для управления графиком.", show_alert=True)
        return
    
    await callback_query.message.answer(
        "📅 <b>График на месяц</b>\n\n"
        "Введите график в формате:\n"
        "<code>ФИО: ДД.ММ.ГГГГ</code>\n"
        "<code>ФИО: ДД.ММ.ГГГГ</code>\n\n"
        "Пример:\n"
        "<code>Иванов И.И.: 01.02.2025</code>\n"
        "<code>Петров П.П.: 02.02.2025</code>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(ScheduleMonth.waiting_for_schedule)
    await callback_query.answer()


async def process_schedule_month(message: types.Message, state: FSMContext):
    """Обработка добавления графика на месяц"""
    lines = message.text.strip().split('\n')
    entries = []
    errors = []
    
    for line in lines:
        if not line.strip():
            continue
        
        if ':' not in line:
            errors.append(f"Неверный формат строки: {line}")
            continue
        
        fio_part, date_part = line.split(':', 1)
        fio = fio_part.strip()
        date_str = date_part.strip()
        
        try:
            # Проверяем формат даты
            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            entries.append((fio, date_str))
        except Exception:
            errors.append(f"Неверный формат даты: {date_str} (ожидается ДД.ММ.ГГГГ)")
    
    if entries:
        # Добавляем каждую запись отдельно
        for fio, date_str in entries:
            await add_coffee_schedule_entry(fio, date_str, message.from_user.id)
        
        await message.answer(
            f"✅ <b>График успешно сохранён!</b>\n\n"
            f"📊 <b>Количество записей:</b> {len(entries)}",
            parse_mode=ParseMode.HTML
        )
        
        # Логируем действие
        await log_admin_action(message.from_user.id, f"added_coffee_schedule_{len(entries)}_entries")
    
    if errors:
        error_text = "❌ <b>Ошибки:</b>\n\n" + "\n".join(errors)
        await message.answer(error_text, parse_mode=ParseMode.HTML)
    
    await state.clear()
    
    # Возвращаемся в главное меню
    from handlers.common_handlers import send_main_menu
    await send_main_menu(message, user_id=message.from_user.id)


def register_moderator_handlers(dp: Dispatcher):
    """Регистрирует обработчики для модераторов"""
    
    # Панели
    dp.callback_query.register(
        moderator_panel_callback,
        lambda c: c.data == "moderator_panel"
    )
    
    dp.callback_query.register(
        marketer_panel_callback,
        lambda c: c.data == "marketer_panel"
    )
    
    # Управление новостями
    dp.callback_query.register(
        publish_news_callback,
        lambda c: c.data == "publish_news"
    )
    
    dp.message.register(
        process_moderator_news,
        Moderator.waiting_for_news
    )
    
    dp.callback_query.register(
        news_proposals_callback,
        lambda c: c.data == "news_proposals"
    )
    
    dp.callback_query.register(
        approve_news_callback,
        lambda c: c.data and c.data.startswith("approve_news_")
    )
    
    dp.callback_query.register(
        reject_news_callback,
        lambda c: c.data and c.data.startswith("reject_news_")
    )
    
    # График кофе
    dp.callback_query.register(
        coffee_schedule_callback,
        lambda c: c.data == "coffee_schedule"
    )
    
    dp.callback_query.register(
        schedule_month_callback,
        lambda c: c.data == "schedule_month"
    )
    
    dp.message.register(
        process_schedule_month,
        ScheduleMonth.waiting_for_schedule
    ) 