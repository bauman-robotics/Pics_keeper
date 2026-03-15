"""
Утилиты для работы с файлами
"""
import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


def ensure_directory(path: str) -> Path:
    """
    Создание директории, если она не существует
    
    Args:
        path: путь к директории
        
    Returns:
        объект Path
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def load_json(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Загрузка JSON файла
    
    Args:
        file_path: путь к файлу
        
    Returns:
        словарь с данными или None при ошибке
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON {file_path}: {e}")
        return None


def save_json(file_path: str, data: Dict[str, Any], pretty: bool = True) -> bool:
    """
    Сохранение данных в JSON файл
    
    Args:
        file_path: путь к файлу
        data: данные для сохранения
        pretty: форматировать с отступами
        
    Returns:
        True при успехе, False при ошибке
    """
    try:
        path = Path(file_path)
        ensure_directory(str(path.parent))
        
        with open(path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(data, f, indent=4, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving JSON {file_path}: {e}")
        return False


def load_yaml(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Загрузка YAML файла
    
    Args:
        file_path: путь к файлу
        
    Returns:
        словарь с данными или None при ошибке
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML {file_path}: {e}")
        return None


def save_yaml(file_path: str, data: Dict[str, Any]) -> bool:
    """
    Сохранение данных в YAML файл
    
    Args:
        file_path: путь к файлу
        data: данные для сохранения
        
    Returns:
        True при успехе, False при ошибке
    """
    try:
        path = Path(file_path)
        ensure_directory(str(path.parent))
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        
        return True
    except Exception as e:
        print(f"Error saving YAML {file_path}: {e}")
        return False


def find_files_by_extension(directory: str, extension: str) -> list:
    """
    Поиск файлов с заданным расширением в директории
    
    Args:
        directory: директория для поиска
        extension: расширение файлов (например, '.yaml')
        
    Returns:
        список найденных файлов
    """
    path = Path(directory)
    if not path.exists():
        return []
    
    return [str(p) for p in path.glob(f"*{extension}")]
