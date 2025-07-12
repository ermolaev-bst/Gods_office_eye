import aiosqlite
import logging
import datetime
from config import ADMIN_ID, DB_PATH

logger = logging.getLogger(__name__)

async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS authorized_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    fio TEXT,
                    position TEXT,
                    role TEXT DEFAULT 'user'
                )
            ''')
            async with conn.execute("PRAGMA table_info(authorized_users)") as cursor:
                columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            if 'role' not in column_names:
                await conn.execute('ALTER TABLE authorized_users ADD COLUMN role TEXT DEFAULT "user"')
                logger.info("Добавлен столбец role в authorized_users.")
            
            # Новая таблица для предложений новостей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS news_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    fio TEXT,
                    news_text TEXT,
                    photos TEXT,  -- JSON массив с file_id фотографий
                    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
                    marketer_id INTEGER,
                    marketer_comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed_at DATETIME
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS auth_requests (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    fio TEXT,
                    position TEXT
                )
            ''')
            # Улучшенная таблица для графика кофемашины
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS coffee_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fio TEXT NOT NULL,
                    date TEXT NOT NULL,
                    user_id INTEGER,
                    created_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notified_at DATETIME,
                    reminder_sent_at DATETIME
                )
            ''')
            
            # Проверяем и добавляем недостающие колонки
            async with conn.execute("PRAGMA table_info(coffee_schedule)") as cursor:
                columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'id' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT')
            if 'user_id' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN user_id INTEGER')
            if 'created_by' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN created_by INTEGER')
            if 'created_at' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP')
            if 'notified_at' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN notified_at DATETIME')
            if 'reminder_sent_at' not in column_names:
                await conn.execute('ALTER TABLE coffee_schedule ADD COLUMN reminder_sent_at DATETIME')
            
            logger.info("Таблица coffee_schedule обновлена.")
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT,
                    target_user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")

async def ensure_auth_requests_timestamp_column():
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("PRAGMA table_info(auth_requests)") as cursor:
            columns = await cursor.fetchall()
        col_names = {col[1] for col in columns}
        if 'timestamp' not in col_names:
            logger.info("Столбец 'timestamp' отсутствует в таблице auth_requests. Добавляю столбец...")
            await conn.execute("ALTER TABLE auth_requests ADD COLUMN timestamp TEXT")
            await conn.commit()
            logger.info("Столбец 'timestamp' успешно добавлен.")

async def init_channel_subscribers_table():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS channel_subscribers (
                    user_id INTEGER PRIMARY KEY,
                    fio TEXT,
                    username TEXT,
                    subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            async with conn.execute("PRAGMA table_info(channel_subscribers)") as cursor:
                columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            if 'username' not in column_names:
                await conn.execute('ALTER TABLE channel_subscribers ADD COLUMN username TEXT')
                logger.info("Добавлен столбец username в channel_subscribers.")
            if 'subscribed_at' not in column_names:
                await conn.execute('ALTER TABLE channel_subscribers ADD COLUMN subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP')
                logger.info("Добавлен столбец subscribed_at в channel_subscribers.")
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы подписчиков: {e}")

# Новая таблица для уведомлённых подписчиков канала
async def init_notified_channel_subscribers_table():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS notified_channel_subscribers (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            await conn.commit()
            logger.info("Таблица notified_channel_subscribers инициализирована.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы notified_channel_subscribers: {e}")

async def add_notified_channel_subscriber(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("INSERT OR IGNORE INTO notified_channel_subscribers (user_id) VALUES (?)", (user_id,))
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка добавления уведомлённого подписчика {user_id}: {e}")

async def get_notified_channel_subscribers():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute("SELECT user_id FROM notified_channel_subscribers") as cursor:
                rows = await cursor.fetchall()
            return {row[0] for row in rows}
    except Exception as e:
        logger.error(f"Ошибка получения уведомлённых подписчиков: {e}")
        return set()

# Новая таблица для уведомлённых пользователей бота
async def init_notified_bot_users_table():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS notified_bot_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            await conn.commit()
            logger.info("Таблица notified_bot_users инициализирована.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы notified_bot_users: {e}")

async def add_notified_bot_user(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("INSERT OR IGNORE INTO notified_bot_users (user_id) VALUES (?)", (user_id,))
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка добавления уведомлённого пользователя {user_id}: {e}")

async def get_notified_bot_users():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute("SELECT user_id FROM notified_bot_users") as cursor:
                rows = await cursor.fetchall()
            return {row[0] for row in rows}
    except Exception as e:
        logger.error(f"Ошибка получения уведомлённых пользователей: {e}")
        return set()

async def assign_roles():
    """Назначает роль администратора главному админу из конфигурации"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('UPDATE authorized_users SET role = "admin" WHERE user_id = ?', (ADMIN_ID,))
            await conn.commit()
            logger.info("Роль администратора назначена главному админу.")
    except Exception as e:
        logger.error(f"Ошибка при назначении роли администратора: {e}")

async def add_auth_request(user_id: int, username: str, fio: str, position: str):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'INSERT OR IGNORE INTO auth_requests (user_id, username, fio, position) VALUES (?, ?, ?, ?)',
                (user_id, username, fio, position)
            )
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка добавления заявки: {e}")

async def get_pending_requests():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT * FROM auth_requests') as cursor:
                requests_list = await cursor.fetchall()
            return requests_list
    except Exception as e:
        logger.error(f"Ошибка получения заявок: {e}")
        return []

async def approve_user(user_id: int):
    try:
        logger.debug(f"DB: approve_user({user_id})")
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT username, fio, position FROM auth_requests WHERE user_id = ?', (user_id,)) as cursor:
                user_data = await cursor.fetchone()
            if user_data:
                username, fio, position = user_data
                logger.debug(f"DB: approve_user found request for {user_id}: {fio}, {position}")
                await conn.execute(
                    'INSERT INTO authorized_users (user_id, username, fio, position) VALUES (?, ?, ?, ?)',
                    (user_id, username, fio, position)
                )
                await conn.execute('DELETE FROM auth_requests WHERE user_id = ?', (user_id,))
                await conn.commit()
                logger.debug(f"DB: approve_user completed for {user_id}")
            else:
                logger.debug(f"DB: approve_user no request found for {user_id}")
    except Exception as e:
        logger.error(f"Ошибка одобрения пользователя: {e}")

async def remove_user(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('DELETE FROM authorized_users WHERE user_id = ?', (user_id,))
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя: {e}")

async def is_authorized(user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT * FROM authorized_users WHERE user_id = ?', (user_id,)) as cursor:
                user = await cursor.fetchone()
            is_auth = user is not None
            logger.debug(f"DB: is_authorized({user_id}) = {is_auth}")
            return is_auth
    except Exception as e:
        logger.error(f"Ошибка проверки авторизации: {e}")
        return False

async def get_authorized_users():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT user_id, username, fio, position, role FROM authorized_users ORDER BY fio') as cursor:
                users = await cursor.fetchall()
            return users
    except Exception as e:
        logger.error(f"Ошибка получения авторизованных пользователей: {e}")
        return []

async def get_user_role(user_id: int) -> str:
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT role FROM authorized_users WHERE user_id = ?', (user_id,)) as cursor:
                role = await cursor.fetchone()
            user_role = role[0] if role else 'user'
            logger.debug(f"DB: get_user_role({user_id}) = {user_role}")
            return user_role
    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя: {e}")
        return 'user'

async def log_admin_action(admin_id: int, action: str, target_user_id: int = None):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'INSERT INTO admin_logs (admin_id, action, target_user_id) VALUES (?, ?, ?)',
                (admin_id, action, target_user_id)
            )
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка логирования действия администратора: {e}")

async def add_channel_subscriber(user_id: int, username: str, fio: str):
    """Добавляет подписчика канала в базу данных"""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            INSERT OR REPLACE INTO channel_subscribers (user_id, username, fio, subscribed_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, fio, datetime.datetime.now().isoformat()))
        await conn.commit()

async def get_channel_subscribers():
    """Получает список всех подписчиков канала"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("""
            SELECT user_id, username, fio, subscribed_at FROM channel_subscribers
            ORDER BY subscribed_at DESC
        """)
        return await cursor.fetchall()

async def remove_channel_subscriber(user_id: int):
    """Удаляет подписчика канала из базы данных"""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM channel_subscribers WHERE user_id = ?", (user_id,))
        await conn.commit()

async def is_channel_subscriber(user_id: int):
    """Проверяет, является ли пользователь подписчиком канала"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT 1 FROM channel_subscribers WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        return result is not None

async def is_fio_already_subscribed(fio: str) -> bool:
    """Проверяет, есть ли уже подписчик с таким ФИО"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT 1 FROM channel_subscribers WHERE LOWER(fio) = LOWER(?)", (fio,))
        result = await cursor.fetchone()
        return result is not None

async def get_subscriber_by_fio(fio: str):
    """Получает информацию о подписчике по ФИО"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT user_id, username, fio, subscribed_at FROM channel_subscribers WHERE LOWER(fio) = LOWER(?)", (fio,))
        return await cursor.fetchone()

async def remove_subscriber_by_fio(fio: str):
    """Удаляет подписчика по ФИО"""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM channel_subscribers WHERE LOWER(fio) = LOWER(?)", (fio,))
        await conn.commit()

# Дублированная функция add_auth_request удалена - используйте функцию выше

# Новые функции для работы с предложениями новостей
# Дублированные функции удалены - используйте функции ниже

async def get_marketers():
    """Получает список всех маркетологов"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT user_id, fio FROM authorized_users WHERE role = "marketer"') as cursor:
                marketers = await cursor.fetchall()
            logger.debug(f"DB: get_marketers found {len(marketers)} marketers")
            return marketers
    except Exception as e:
        logger.error(f"Ошибка получения списка маркетологов: {e}")
        return []

# Старая функция add_coffee_schedule удалена - используйте add_coffee_schedule_entry

async def update_news_proposal_content(proposal_id: int, news_text: str, photos_json: str = None):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            if photos_json is not None:
                await conn.execute(
                    'UPDATE news_proposals SET news_text = ?, photos = ? WHERE id = ?',
                    (news_text, photos_json, proposal_id)
                )
            else:
                await conn.execute(
                    'UPDATE news_proposals SET news_text = ? WHERE id = ?',
                    (news_text, proposal_id)
                )
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка обновления содержания предложения новости: {e}")

async def get_pending_auth_requests():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT user_id, username, fio, position, timestamp FROM auth_requests') as cursor:
                requests_list = await cursor.fetchall()
            return requests_list
    except Exception as e:
        logger.error(f"Ошибка получения заявок: {e}")
        return []

async def get_user_info(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT * FROM authorized_users WHERE user_id = ?', (user_id,)) as cursor:
                user_info = await cursor.fetchone()
            return user_info
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
        return None

async def add_news_proposal(user_id: int, username: str, fio: str, news_text: str, photos_json: str):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'INSERT INTO news_proposals (user_id, username, fio, news_text, photos) VALUES (?, ?, ?, ?, ?)',
                (user_id, username, fio, news_text, photos_json)
            ) as cursor:
                await conn.commit()
                return cursor.lastrowid
    except Exception as e:
        logger.error(f"Ошибка добавления предложения новости: {e}")
        return None

async def get_pending_news_proposals():
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id, user_id, username, fio, news_text, photos, status, marketer_id, marketer_comment, created_at, processed_at FROM news_proposals WHERE status = "pending" ORDER BY created_at DESC'
            ) as cursor:
                proposals = await cursor.fetchall()
            return proposals
    except Exception as e:
        logger.error(f"Ошибка получения предложений новостей: {e}")
        return []

async def update_news_proposal_status(proposal_id: int, status: str, marketer_id: int, comment: str = None):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'UPDATE news_proposals SET status = ?, marketer_id = ?, marketer_comment = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?',
                (status, marketer_id, comment, proposal_id)
            )
            await conn.commit()
    except Exception as e:
        logger.error(f"Ошибка обновления статуса предложения {proposal_id}: {e}")

async def get_news_proposal_by_id(proposal_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT id, user_id, username, fio, news_text, photos, status, marketer_id, marketer_comment, created_at, processed_at FROM news_proposals WHERE id = ?',
                (proposal_id,)
            ) as cursor:
                proposal = await cursor.fetchone()
            return proposal
    except Exception as e:
        logger.error(f"Ошибка получения предложения {proposal_id}: {e}")
        return None

# Функции для работы с графиком кофемашины
async def add_coffee_schedule_entry(fio: str, date: str, created_by: int, user_id: int = None):
    """Добавляет запись в график кофемашины"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'INSERT INTO coffee_schedule (fio, date, user_id, created_by) VALUES (?, ?, ?, ?)',
                (fio, date, user_id, created_by)
            )
            await conn.commit()
            logger.info(f"Добавлена запись в график кофе: {fio} на {date}")
    except Exception as e:
        logger.error(f"Ошибка добавления записи в график кофе: {e}")

async def get_coffee_schedule_by_date(date: str):
    """Получает записи графика кофемашины на определенную дату"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Структура таблицы coffee_schedule для даты {date}: {column_names}")
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'SELECT id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE date = ? ORDER BY fio'
            else:
                query = 'SELECT rowid, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE date = ? ORDER BY fio'
            
            logger.info(f"Выполняем запрос для даты {date}: {query}")
            async with conn.execute(query, (date,)) as cursor:
                entries = await cursor.fetchall()
            logger.info(f"Получено {len(entries)} записей для даты {date}")
            for i, entry in enumerate(entries):
                logger.info(f"Запись {i} для даты {date}: {entry}")
            return entries
    except Exception as e:
        logger.error(f"Ошибка получения графика кофе на {date}: {e}")
        return []

async def get_coffee_schedule_by_fio(fio: str):
    """Получает записи графика кофемашины для определенного ФИО"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Структура таблицы coffee_schedule: {column_names}")
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'SELECT id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE fio = ? ORDER BY date'
            else:
                query = 'SELECT rowid, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE fio = ? ORDER BY date'
            
            logger.info(f"Выполняем запрос для {fio}: {query}")
            async with conn.execute(query, (fio,)) as cursor:
                entries = await cursor.fetchall()
            logger.info(f"Получено {len(entries)} записей для {fio}")
            for i, entry in enumerate(entries):
                logger.info(f"Запись {i} для {fio}: {entry}")
            return entries
    except Exception as e:
        logger.error(f"Ошибка получения графика кофе для {fio}: {e}")
        return []

async def get_all_coffee_schedule():
    """Получает весь график кофемашины"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Структура таблицы coffee_schedule: {column_names}")
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'SELECT id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule ORDER BY date, fio'
            else:
                query = 'SELECT rowid, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule ORDER BY date, fio'
            
            logger.info(f"Выполняем запрос: {query}")
            async with conn.execute(query) as cursor:
                entries = await cursor.fetchall()
            logger.info(f"Получено {len(entries)} записей из базы данных")
            for i, entry in enumerate(entries):
                logger.info(f"Запись {i}: {entry}")
            return entries
    except Exception as e:
        logger.error(f"Ошибка получения всего графика кофе: {e}")
        return []

async def get_today_coffee_schedule():
    """Получает записи графика кофемашины на сегодня"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_dd_mm_yyyy = datetime.datetime.now().strftime('%d.%m.%Y')
        
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Структура таблицы coffee_schedule для проверки: {column_names}")
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'SELECT id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE (date = ? OR date = ?) AND reminder_sent_at IS NULL'
            else:
                query = 'SELECT rowid, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE (date = ? OR date = ?) AND reminder_sent_at IS NULL'
            
            logger.info(f"Выполняем запрос для проверки: {query}")
            async with conn.execute(query, (today, today_dd_mm_yyyy)) as cursor:
                entries = await cursor.fetchall()
            logger.info(f"Получено {len(entries)} записей для проверки из базы данных")
            for i, entry in enumerate(entries):
                logger.info(f"Запись для проверки {i}: {entry}")
            return entries
    except Exception as e:
        logger.error(f"Ошибка получения графика кофе на сегодня: {e}")
        return []

async def get_today_coffee_schedule_for_notification():
    """Получает записи графика кофемашины на сегодня для отправки уведомлений"""
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        today_dd_mm_yyyy = datetime.datetime.now().strftime('%d.%m.%Y')
        
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"Структура таблицы coffee_schedule для уведомлений: {column_names}")
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'SELECT id, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE (date = ? OR date = ?) AND notified_at IS NULL'
            else:
                query = 'SELECT rowid, fio, date, user_id, created_by, created_at, notified_at, reminder_sent_at FROM coffee_schedule WHERE (date = ? OR date = ?) AND notified_at IS NULL'
            
            logger.info(f"Выполняем запрос для уведомлений: {query}")
            async with conn.execute(query, (today, today_dd_mm_yyyy)) as cursor:
                entries = await cursor.fetchall()
            logger.info(f"Получено {len(entries)} записей для уведомлений из базы данных")
            for i, entry in enumerate(entries):
                logger.info(f"Запись для уведомления {i}: {entry}")
            return entries
    except Exception as e:
        logger.error(f"Ошибка получения графика кофе на сегодня для уведомлений: {e}")
        return []

async def mark_coffee_notification_sent_by_fio(fio: str, date: str):
    """Отмечает, что уведомление о графике отправлено по ФИО и дате"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                'UPDATE coffee_schedule SET notified_at = CURRENT_TIMESTAMP WHERE fio = ? AND date = ?',
                (fio, date)
            )
            await conn.commit()
            logger.info(f"Отмечено отправление уведомления для {fio} на {date}")
    except Exception as e:
        logger.error(f"Ошибка отметки отправления уведомления для {fio}: {e}")

async def mark_coffee_reminder_sent(entry_id: int):
    """Отмечает, что напоминание о кофе отправлено"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'UPDATE coffee_schedule SET reminder_sent_at = CURRENT_TIMESTAMP WHERE id = ?'
            else:
                query = 'UPDATE coffee_schedule SET reminder_sent_at = CURRENT_TIMESTAMP WHERE rowid = ?'
            
            await conn.execute(query, (entry_id,))
            await conn.commit()
            logger.info(f"Отмечено отправление напоминания для записи {entry_id}")
    except Exception as e:
        logger.error(f"Ошибка отметки отправления напоминания: {e}")

async def mark_coffee_notification_sent(entry_id: int):
    """Отмечает, что уведомление о графике отправлено"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем структуру таблицы
            cursor = await conn.execute("PRAGMA table_info(coffee_schedule)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Если есть колонка id, используем её, иначе используем rowid
            if 'id' in column_names:
                query = 'UPDATE coffee_schedule SET notified_at = CURRENT_TIMESTAMP WHERE id = ?'
            else:
                query = 'UPDATE coffee_schedule SET notified_at = CURRENT_TIMESTAMP WHERE rowid = ?'
            
            await conn.execute(query, (entry_id,))
            await conn.commit()
            logger.info(f"Отмечено отправление уведомления для записи {entry_id}")
    except Exception as e:
        logger.error(f"Ошибка отметки отправления уведомления: {e}")

async def clear_coffee_schedule():
    """Очищает весь график кофемашины"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('DELETE FROM coffee_schedule')
            await conn.commit()
            logger.info("График кофемашины очищен")
    except Exception as e:
        logger.error(f"Ошибка очистки графика кофе: {e}")

async def clean_invalid_coffee_entries():
    """Удаляет записи с некорректными данными из графика кофемашины"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем, сколько записей с проблемами
            cursor = await conn.execute('SELECT COUNT(*) FROM coffee_schedule WHERE date IS NULL OR date = ""')
            null_dates = (await cursor.fetchone())[0]
            
            cursor = await conn.execute('SELECT COUNT(*) FROM coffee_schedule WHERE fio IS NULL OR fio = ""')
            null_fios = (await cursor.fetchone())[0]
            
            logger.info(f"Найдено записей с пустыми датами: {null_dates}")
            logger.info(f"Найдено записей с пустыми ФИО: {null_fios}")
            
            # Удаляем записи с NULL датами
            await conn.execute('DELETE FROM coffee_schedule WHERE date IS NULL OR date = ""')
            # Удаляем записи с пустыми ФИО
            await conn.execute('DELETE FROM coffee_schedule WHERE fio IS NULL OR fio = ""')
            await conn.commit()
            logger.info("Некорректные записи графика кофемашины очищены")
    except Exception as e:
        logger.error(f"Ошибка очистки некорректных записей графика кофе: {e}")

async def fix_null_dates_in_coffee_schedule():
    """Исправляет записи с NULL датами, устанавливая сегодняшнюю дату"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем, сколько записей с NULL датами
            cursor = await conn.execute('SELECT COUNT(*) FROM coffee_schedule WHERE date IS NULL')
            null_dates = (await cursor.fetchone())[0]
            
            if null_dates == 0:
                logger.info("Записей с NULL датами не найдено")
                return 0
            
            logger.info(f"Найдено {null_dates} записей с NULL датами")
            
            # Получаем все записи с NULL датами
            cursor = await conn.execute('SELECT rowid, fio FROM coffee_schedule WHERE date IS NULL')
            entries = await cursor.fetchall()
            
            fixed_count = 0
            today = datetime.datetime.now().strftime('%d.%m.%Y')
            
            for entry_id, fio in entries:
                try:
                    # Устанавливаем сегодняшнюю дату
                    await conn.execute(
                        'UPDATE coffee_schedule SET date = ? WHERE rowid = ?',
                        (today, entry_id)
                    )
                    logger.info(f"Исправлена запись {entry_id} для {fio}: установлена дата {today}")
                    fixed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка исправления записи {entry_id}: {e}")
            
            await conn.commit()
            logger.info(f"Исправлено {fixed_count} записей с NULL датами")
            return fixed_count
            
    except Exception as e:
        logger.error(f"Ошибка исправления NULL дат в графике кофе: {e}")
        return 0

async def get_user_id_by_fio(fio: str):
    """Получает user_id по ФИО из авторизованных пользователей"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT user_id FROM authorized_users WHERE LOWER(fio) = LOWER(?)',
                (fio,)
            ) as cursor:
                result = await cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка получения user_id для {fio}: {e}")
        return None

async def get_user_by_fio(fio: str):
    """Получает полную информацию о пользователе по ФИО из авторизованных пользователей"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT * FROM authorized_users WHERE LOWER(fio) = LOWER(?)',
                (fio,)
            ) as cursor:
                result = await cursor.fetchone()
            return result
    except Exception as e:
        logger.error(f"Ошибка получения пользователя для {fio}: {e}")
        return None

async def get_all_authorized_user_ids():
    """Получает список всех ID авторизованных пользователей для очистки клавиатур"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT user_id FROM authorized_users') as cursor:
                rows = await cursor.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        return []

async def assign_user_role(user_id: int, role: str, admin_id: int = None):
    """Назначает роль пользователю (только для администраторов)"""
    try:
        # Проверяем, что роль валидна
        valid_roles = ['user', 'moderator', 'admin', 'marketer']
        if role not in valid_roles:
            raise ValueError(f"Неверная роль: {role}. Допустимые роли: {valid_roles}")
        
        async with aiosqlite.connect(DB_PATH) as conn:
            # Проверяем, что пользователь существует
            async with conn.execute('SELECT 1 FROM authorized_users WHERE user_id = ?', (user_id,)) as cursor:
                user_exists = await cursor.fetchone()
            
            if not user_exists:
                raise ValueError(f"Пользователь с ID {user_id} не найден")
            
            # Обновляем роль
            await conn.execute('UPDATE authorized_users SET role = ? WHERE user_id = ?', (role, user_id))
            await conn.commit()
            
            # Логируем действие
            if admin_id:
                await log_admin_action(admin_id, f"assign_role_{role}", user_id)
            
            logger.info(f"Роль {role} назначена пользователю {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"Ошибка назначения роли {role} пользователю {user_id}: {e}")
        return False

async def get_users_by_role(role: str):
    """Получает список пользователей по роли"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                'SELECT user_id, username, fio, position, role FROM authorized_users WHERE role = ? ORDER BY fio', 
                (role,)
            ) as cursor:
                users = await cursor.fetchall()
            return users
    except Exception as e:
        logger.error(f"Ошибка получения пользователей с ролью {role}: {e}")
        return []

async def migrate_roles_from_env():
    """Автоматическая миграция ролей из переменных окружения в базу данных"""
    try:
        import os
        from dotenv import load_dotenv
        
        # Загружаем переменные окружения
        load_dotenv()
        
        # Получаем старые значения из переменных окружения
        old_moderator_id = os.getenv("MODERATOR_ID")
        old_marketer_id = os.getenv("MARKETER_ID")
        
        if not old_moderator_id and not old_marketer_id:
            logger.info("Миграция ролей: старые переменные ролей не найдены")
            return
        
        logger.info("🔄 Начинаем автоматическую миграцию ролей...")
        
        async with aiosqlite.connect(DB_PATH) as conn:
            migrated_count = 0
            
            # Назначаем роль модератора
            if old_moderator_id:
                try:
                    moderator_id = int(old_moderator_id)
                    await conn.execute(
                        'UPDATE authorized_users SET role = "moderator" WHERE user_id = ?', 
                        (moderator_id,)
                    )
                    logger.info(f"✅ Роль модератора назначена пользователю {moderator_id}")
                    migrated_count += 1
                except ValueError:
                    logger.error(f"❌ Неверный формат MODERATOR_ID: {old_moderator_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка назначения роли модератора: {e}")
            
            # Назначаем роль маркетолога
            if old_marketer_id:
                try:
                    marketer_id = int(old_marketer_id)
                    await conn.execute(
                        'UPDATE authorized_users SET role = "marketer" WHERE user_id = ?', 
                        (marketer_id,)
                    )
                    logger.info(f"✅ Роль маркетолога назначена пользователю {marketer_id}")
                    migrated_count += 1
                except ValueError:
                    logger.error(f"❌ Неверный формат MARKETER_ID: {old_marketer_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка назначения роли маркетолога: {e}")
            
            await conn.commit()
            
            if migrated_count > 0:
                logger.info(f"✅ Миграция ролей завершена. Назначено ролей: {migrated_count}")
                logger.warning("⚠️ Рекомендуется удалить MODERATOR_ID и MARKETER_ID из .env файла")
            else:
                logger.info("ℹ️ Миграция ролей не потребовалась")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматической миграции ролей: {e}")

async def cleanup_env_roles():
    """Удаляет старые переменные ролей из .env файла"""
    try:
        import os
        import re
        
        env_file = '.env'
        
        if not os.path.exists(env_file):
            logger.debug("Файл .env не найден, пропускаем очистку")
            return
        
        # Читаем файл
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие старых переменных
        old_vars = []
        if 'MODERATOR_ID=' in content:
            old_vars.append('MODERATOR_ID')
        if 'MARKETER_ID=' in content:
            old_vars.append('MARKETER_ID')
        
        if not old_vars:
            logger.debug("Старые переменные ролей не найдены в .env")
            return
        
        # Удаляем строки с старыми переменными
        lines = content.split('\n')
        new_lines = []
        removed_count = 0
        
        for line in lines:
            if not re.match(r'^(MODERATOR_ID|MARKETER_ID)\s*=', line.strip()):
                new_lines.append(line)
            else:
                removed_count += 1
        
        # Записываем обновленный файл
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        if removed_count > 0:
            logger.info(f"✅ Удалено {removed_count} старых переменных ролей из .env файла")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке .env файла: {e}")
