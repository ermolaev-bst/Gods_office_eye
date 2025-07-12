import hashlib
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def load_excel(file_path):
    """
    Загружает Excel-файл и гарантирует наличие колонки 'Фото'.
    Если ячейка пустая или NaN — будет None.
    """
    try:
        df = pd.read_excel(file_path)
        # —————— Обеспечиваем колонку Фото ——————
        if 'Фото' not in df.columns:
            df['Фото'] = None
        else:
            # приводим всё к строке, обрезаем пробелы
            df['Фото'] = df['Фото'].astype(str).str.strip()
            # пустые строки или 'nan' превращаем в None
            df.loc[df['Фото'].isin(['', 'nan', 'None', 'NaN']), 'Фото'] = None
        return df
    except Exception as e:
        logger.error(f"Ошибка при загрузке Excel-файла: {e}")
        # возвращаем DataFrame с нужными колонками, чтобы код не падал
        cols = ['ФИО', 'Должность', 'Отдел', 'Фото']
        return pd.DataFrame(columns=cols)

def search_by_fio(df, fio):
    """Ищет данные по ФИО."""
#    return df[df['ФИО'].str.contains(fio, case=False, na=False)]
    mask = df['ФИО'].fillna('').astype(str).str.contains(fio, case=False)
    return df[mask]


def search_by_position(df, position):
    """Ищет данные по должности."""
#    return df[df['Должность'].str.contains(position, case=False, na=False)]
    mask = df['Должность'].fillna('').astype(str).str.contains(position, case=False)
    return df[mask]


def search_by_department(df, department):
    """Ищет данные по отделу."""
#    return df[df['Отдел'].str.contains(department, case=False, na=False)]
    mask = df['Отдел'].fillna('').astype(str).str.contains(department, case=False)
    return df[mask]

class DataManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = load_excel(file_path)
        self.previous_hash = self.get_file_hash()

    def get_file_hash(self):
        hasher = hashlib.md5()
        try:
            with open(self.file_path, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
        except Exception as e:
            logger.error(f"Ошибка при вычислении хэша файла: {e}")
        return hasher.hexdigest()

    def reload_excel(self):
        self.df = load_excel(self.file_path)
        self.previous_hash = self.get_file_hash()

    def check_updates(self):
        current_hash = self.get_file_hash()
        messages = []
        if current_hash != self.previous_hash:
            old_df = self.df.copy()
            self.df = load_excel(self.file_path)
            self.previous_hash = current_hash

            if 'ФИО' in self.df.columns and 'Должность' in self.df.columns:
                new_employees = self.df[~self.df['ФИО'].isin(old_df['ФИО'])]
                for _, row in new_employees.iterrows():
                    messages.append(f"🎉 Добро пожаловать в команду, {row['ФИО']} ({row['Должность']})! 🎉")
                removed_employees = old_df[~old_df['ФИО'].isin(self.df['ФИО'])]
                for _, row in removed_employees.iterrows():
                    messages.append(f"😢 Спасибо за работу, {row['ФИО']} ({row['Должность']}). Мы будем скучать! 😢")
        return messages
