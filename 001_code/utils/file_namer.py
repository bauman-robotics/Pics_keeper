#!/usr/bin/env python3
"""
Утилита для формирования имен файлов на основе YAML конфигурации
"""

import os
import yaml
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class FileNamer:
    """Класс для генерации имен файлов по шаблону из YAML конфигурации"""
    
    def __init__(self, config_path: str = '001_code/config/file_naming.yaml'):
        """
        Инициализация FileNamer
        
        Args:
            config_path: Путь к YAML конфигурационному файлу
        """
        # Определяем базовую директорию (где находится main.py)
        import inspect
        frame = inspect.currentframe()
        try:
            # Идем вверх по стеку, пока не найдем main.py
            while frame:
                filename = frame.f_code.co_filename
                if filename.endswith('main.py'):
                    base_dir = os.path.dirname(os.path.abspath(filename))
                    project_root = os.path.dirname(base_dir)
                    break
                frame = frame.f_back
            else:
                # Если не нашли main.py, используем текущую директорию
                project_root = os.getcwd()
        finally:
            del frame
        
        # Создаем абсолютный путь к конфигурационному файлу
        if not os.path.isabs(config_path):
            config_path = os.path.join(project_root, config_path)
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из YAML файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"⚠️  Конфигурационный файл не найден: {self.config_path}")
            print("   Используются настройки по умолчанию")
            return self._get_default_config()
        except yaml.YAMLError as e:
            print(f"❌ Ошибка чтения YAML конфигурации: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию по умолчанию"""
        return {
            'file_format': '{prefix}_{camera}_{date}_{time}_{number}.{extension}',
            'prefix': 'chessboard',
            'extension': 'jpg',
            'date_format': '%Y%m%d',
            'time_format': '%H%M%S',
            'number_format': '03d',
            'default_save_dir': '003_pics',
            'naming': {
                'allow_overwrite': False,
                'max_attempts': 100,
                'strict_numbering': True
            }
        }
    
    def generate_filename(self, camera_type: str, save_dir: Optional[str] = None, 
                         timestamp: Optional[float] = None) -> str:
        """
        Генерация имени файла по шаблону
        
        Args:
            camera_type: Тип камеры (imx708, imx415, local_web и т.д.)
            save_dir: Директория для сохранения (если None, используется default_save_dir)
            timestamp: Временная метка (если None, используется текущее время)
        
        Returns:
            Строка с полным путем к файлу
        """
        if save_dir is None:
            save_dir = self.config.get('default_save_dir', '003_pics')
        
        # Определяем базовую директорию (где находится main.py)
        # Ищем main.py в стеке вызовов
        import inspect
        frame = inspect.currentframe()
        try:
            # Идем вверх по стеку, пока не найдем main.py
            while frame:
                filename = frame.f_code.co_filename
                if filename.endswith('main.py'):
                    base_dir = os.path.dirname(os.path.abspath(filename))
                    project_root = os.path.dirname(base_dir)
                    break
                frame = frame.f_back
            else:
                # Если не нашли main.py, используем текущую директорию
                project_root = os.getcwd()
        finally:
            del frame
        
        # Создаем абсолютный путь к директории сохранения
        save_dir = os.path.join(project_root, save_dir)
        
        if timestamp is None:
            timestamp = time.time()
        
        # Создаем директорию если она не существует
        os.makedirs(save_dir, exist_ok=True)
        
        # Форматируем дату и время
        dt = datetime.fromtimestamp(timestamp)
        date_str = dt.strftime(self.config['date_format'])
        time_str = dt.strftime(self.config['time_format'])
        
        # Получаем следующий номер
        next_number = self._get_next_number(save_dir, camera_type)
        
        # Форматируем имя файла
        filename = self.config['file_format'].format(
            prefix=self.config['prefix'],
            camera=camera_type,
            date=date_str,
            time=time_str,
            number=format(next_number, self.config['number_format']),
            extension=self.config['extension']
        )
        
        return os.path.join(save_dir, filename)
    
    def _get_next_number(self, save_dir: str, camera_type: str) -> int:
        """
        Получение следующего номера для файла
        
        Args:
            save_dir: Директория для сохранения
            camera_type: Тип камеры
        
        Returns:
            Следующий номер (целое число)
        """
        if not self.config['naming']['strict_numbering']:
            # Если не используется строгая нумерация, возвращаем случайный номер
            import random
            return random.randint(1, 999)
        
        # Ищем существующие файлы с таким же префиксом и типом камеры
        prefix = self.config['prefix']
        extension = self.config['extension']
        
        existing_files = []
        try:
            for filename in os.listdir(save_dir):
                if filename.startswith(f"{prefix}_{camera_type}_") and filename.endswith(f".{extension}"):
                    existing_files.append(filename)
        except OSError:
            # Директория не существует или недоступна
            return 1
        
        if not existing_files:
            return 1
        
        # Извлекаем номера из имен файлов
        numbers = []
        for filename in existing_files:
            try:
                # Извлекаем часть с номером из имени файла
                # Формат: prefix_camera_date_time_number.extension
                parts = filename.replace(f".{extension}", "").split('_')
                if len(parts) >= 5:  # prefix_camera_date_time_number
                    number_str = parts[-1]
                    if number_str.isdigit():
                        numbers.append(int(number_str))
            except:
                continue
        
        if numbers:
            return max(numbers) + 1
        else:
            return 1
    
    def get_config_info(self) -> Dict[str, Any]:
        """Получение информации о текущей конфигурации"""
        return {
            'file_format': self.config['file_format'],
            'prefix': self.config['prefix'],
            'extension': self.config['extension'],
            'date_format': self.config['date_format'],
            'time_format': self.config['time_format'],
            'number_format': self.config['number_format'],
            'default_save_dir': self.config['default_save_dir'],
            'naming_options': self.config['naming']
        }
    
    def validate_config(self) -> bool:
        """Проверка валидности конфигурации"""
        required_keys = ['file_format', 'prefix', 'extension', 'date_format', 'time_format', 'number_format']
        
        for key in required_keys:
            if key not in self.config:
                print(f"❌ В конфигурации отсутствует обязательный ключ: {key}")
                return False
        
        # Проверяем доступные переменные в формате
        file_format = self.config['file_format']
        required_vars = ['{prefix}', '{camera}', '{date}', '{time}', '{number}', '{extension}']
        
        for var in required_vars:
            if var not in file_format:
                print(f"⚠️  В формате имени файла отсутствует переменная: {var}")
        
        return True

def generate_filename(camera_type: str, save_dir: Optional[str] = None, 
                     timestamp: Optional[float] = None,
                     config_path: str = '001_code/config/file_naming.yaml') -> str:
    """
    Удобная функция для генерации имени файла
    
    Args:
        camera_type: Тип камеры
        save_dir: Директория для сохранения
        timestamp: Временная метка
        config_path: Путь к конфигурационному файлу
    
    Returns:
        Строка с полным путем к файлу
    """
    namer = FileNamer(config_path)
    return namer.generate_filename(camera_type, save_dir, timestamp)

def get_config_info(config_path: str = '001_code/config/file_naming.yaml') -> Dict[str, Any]:
    """Получение информации о конфигурации"""
    namer = FileNamer(config_path)
    return namer.get_config_info()

def validate_config(config_path: str = '001_code/config/file_naming.yaml') -> bool:
    """Проверка валидности конфигурации"""
    namer = FileNamer(config_path)
    return namer.validate_config()