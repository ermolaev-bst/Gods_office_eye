import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHAT_ID = int(os.getenv("CHAT_ID"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
CHANNEL_CHAT_ID = int(os.getenv("CHANNEL_CHAT_ID", "0"))  # ID канала
EXCEL_FILE = os.getenv("EXCEL_FILE")
ADMIN_WEB_PASSWORD = os.getenv("ADMIN_WEB_PASSWORD")
MODERATOR_WEB_PASSWORD = os.getenv("MODERATOR_WEB_PASSWORD")
BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
CHANNEL_USERS_EXCEL = os.getenv("CHANNEL_USERS_EXCEL")  # Excel файл с пользователями канала
DB_PATH = 'bot.db'
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
PYROGRAM_SESSION = os.getenv("PYROGRAM_SESSION")  # Например, "pyrogram_session"
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))
TELETHON_USER_PHONE = os.getenv("TELETHON_USER_PHONE")
INVITE_LINK = os.getenv("INVITE_LINK")  # Ссылка-приглашение в канал

# Настройки Pyrogram для управления каналом
PYROGRAM_API_ID = str(TELEGRAM_API_ID)  # API ID от https://my.telegram.org
PYROGRAM_API_HASH = TELEGRAM_API_HASH  # API Hash от https://my.telegram.org
PYROGRAM_BOT_TOKEN = BOT_TOKEN  # Токен бота (тот же, что и для aiogram)
