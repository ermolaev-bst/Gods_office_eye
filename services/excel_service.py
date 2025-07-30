"""
Сервис для работы с Excel файлами
"""

import pandas as pd
import os
import logging
from typing import List, Dict, Optional, Any
from config import EXCEL_FILE

logger = logging.getLogger(__name__)


class ExcelService:
    """Сервис для работы с Excel файлами"""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or EXCEL_FILE
    
    def load_data(self) -> Optional[pd.DataFrame]:
        """Загружает данные из Excel файла"""
        try:
            if not os.path.exists(self.file_path):
                logger.warning(f"Excel файл не найден: {self.file_path}")
                return None
            
            df = pd.read_excel(self.file_path)
            logger.info(f"Загружено {len(df)} записей из Excel")
            return df
        
        except Exception as e:
            logger.error(f"Ошибка загрузки Excel файла: {e}")
            return None
    
    def search_by_fio(self, query: str) -> List[Dict[str, Any]]:
        """Поиск по ФИО"""
        df = self.load_data()
        if df is None:
            return []
        
        # Поиск по колонке ФИО
        fio_columns = [col for col in df.columns if 'фио' in col.lower()]
        if not fio_columns:
            fio_columns = [df.columns[0]]  # Первая колонка по умолчанию
        
        results = []
        for col in fio_columns:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            matches = df[mask]
            
            for _, row in matches.iterrows():
                results.append(row.to_dict())
        
        return results
    
    def search_by_position(self, query: str) -> List[Dict[str, Any]]:
        """Поиск по должности"""
        df = self.load_data()
        if df is None:
            return []
        
        # Поиск по колонке должности
        position_columns = [col for col in df.columns if 'должность' in col.lower()]
        if not position_columns:
            position_columns = [col for col in df.columns if 'position' in col.lower()]
        
        results = []
        for col in position_columns:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            matches = df[mask]
            
            for _, row in matches.iterrows():
                results.append(row.to_dict())
        
        return results
    
    def search_by_department(self, query: str) -> List[Dict[str, Any]]:
        """Поиск по отделу"""
        df = self.load_data()
        if df is None:
            return []
        
        # Поиск по колонке отдела
        dept_columns = [col for col in df.columns if 'отдел' in col.lower()]
        if not dept_columns:
            dept_columns = [col for col in df.columns if 'department' in col.lower()]
        
        results = []
        for col in dept_columns:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            matches = df[mask]
            
            for _, row in matches.iterrows():
                results.append(row.to_dict())
        
        return results
    
    def search_by_phone(self, query: str) -> List[Dict[str, Any]]:
        """Поиск по телефону"""
        df = self.load_data()
        if df is None:
            return []
        
        # Поиск по колонкам с телефонами
        phone_columns = [col for col in df.columns if 'телефон' in col.lower() or 'phone' in col.lower()]
        
        results = []
        for col in phone_columns:
            mask = df[col].astype(str).str.contains(query, case=False, na=False)
            matches = df[mask]
            
            for _, row in matches.iterrows():
                results.append(row.to_dict())
        
        return results
    
    def export_to_file(self, output_path: str) -> bool:
        """Экспортирует данные в файл"""
        try:
            df = self.load_data()
            if df is None:
                return False
            
            # Определяем формат по расширению
            if output_path.endswith('.xlsx'):
                df.to_excel(output_path, index=False)
            elif output_path.endswith('.csv'):
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            else:
                logger.error(f"Неподдерживаемый формат файла: {output_path}")
                return False
            
            logger.info(f"Данные экспортированы в {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка экспорта данных: {e}")
            return False
    
    def get_column_info(self) -> Dict[str, Any]:
        """Возвращает информацию о колонках"""
        df = self.load_data()
        if df is None:
            return {}
        
        return {
            'columns': list(df.columns),
            'row_count': len(df),
            'column_count': len(df.columns)
        }


# Функции для совместимости
def search_in_excel(query: str, search_type: str = "fio") -> List[Dict[str, Any]]:
    """Поиск в Excel файле"""
    service = ExcelService()
    
    if search_type == "fio":
        return service.search_by_fio(query)
    elif search_type == "position":
        return service.search_by_position(query)
    elif search_type == "department":
        return service.search_by_department(query)
    elif search_type == "phone":
        return service.search_by_phone(query)
    else:
        return []


def export_contacts(output_path: str) -> bool:
    """Экспорт контактов"""
    service = ExcelService()
    return service.export_to_file(output_path) 