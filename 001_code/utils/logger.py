#!/usr/bin/env python3
"""
Модуль логирования для Pics_keeper
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

class PicsKeeperLogger:
    """Класс для логирования событий приложения"""
    
    def __init__(self, camera_type: str = 'unknown', log_dir: str = '002_logs'):
        """
        Инициализация логгера
        
        Args:
            camera_type: Тип камеры для имени файла
            log_dir: Директория для логов
        """
        self.camera_type = camera_type
        
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
        
        # Создаем абсолютный путь к директории логов
        self.log_dir = os.path.join(project_root, log_dir)
        self.logger = None
        self.log_file = None
        
        # Создаем директорию для логов
        self._ensure_log_directory()
        
        # Создаем имя лог-файла
        self._create_log_filename()
        
        # Настраиваем логгер
        self._setup_logger()
    
    def _ensure_log_directory(self):
        """Создание директории для логов если не существует"""
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except Exception as e:
            print(f"❌ Ошибка создания директории логов: {e}")
            sys.exit(1)
    
    def _create_log_filename(self):
        """Создание имени лог-файла с датой-временем и типом камеры"""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        # Нормализуем тип камеры для имени файла
        normalized_camera = self.camera_type.replace('-', '_').replace(' ', '_')
        
        filename = f"pics_keeper_{timestamp}_{normalized_camera}.log"
        self.log_file = os.path.join(self.log_dir, filename)
    
    def _setup_logger(self):
        """Настройка логгера"""
        self.logger = logging.getLogger('pics_keeper')
        self.logger.setLevel(logging.DEBUG)
        
        # Очищаем существующие хендлеры
        self.logger.handlers.clear()
        
        # Формат сообщений
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Хендлер для файла
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Хендлер для консоли
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Добавляем хендлеры к логгеру
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Записываем информацию о запуске
        self.logger.info(f"🚀 Pics_keeper запущен")
        self.logger.info(f"📁 Лог-файл: {self.log_file}")
        self.logger.info(f"📷 Тип камеры: {self.camera_type}")
    
    def log_arguments(self, args, settings=None):
        """Логирование аргументов командной строки с группировкой по функциональным модулям"""
        self.logger.info("📋 Параметры запуска:")
        
        # Функция для получения значения с указанием источника
        def get_value(param_name, default_value=None):
            value = getattr(args, param_name, None)
            if value is not None:
                return f"{value} (указано)"
            elif settings is not None:
                # Пытаемся получить значение из settings
                try:
                    if hasattr(settings, 'camera') and hasattr(settings.camera, param_name):
                        return f"{getattr(settings.camera, param_name)} (по умолчанию)"
                    elif hasattr(settings, 'stream') and hasattr(settings.stream, param_name):
                        return f"{getattr(settings.stream, param_name)} (по умолчанию)"
                    elif hasattr(settings, 'capture') and hasattr(settings.capture, param_name):
                        return f"{getattr(settings.capture, param_name)} (по умолчанию)"
                    elif hasattr(settings, 'debug') and hasattr(settings.debug, param_name):
                        return f"{getattr(settings.debug, param_name)} (по умолчанию)"
                    elif hasattr(settings, param_name):
                        return f"{getattr(settings, param_name)} (по умолчанию)"
                except:
                    pass
            return f"{default_value} (по умолчанию)" if default_value is not None else "не указано"
        
        # 📷 КАМЕРА
        self.logger.info("📷 КАМЕРА:")
        if hasattr(args, 'camera') and args.camera:
            self.logger.info(f"   --camera: {args.camera} (указано)")
        else:
            camera_type = getattr(settings, 'camera', None) and getattr(settings.camera, 'camera_type', 'не указано')
            self.logger.info(f"   --camera: {camera_type} (по умолчанию)")
        
        self.logger.info(f"   --resolution: {get_value('resolution', 'full')}")
        self.logger.info(f"   --exposure-time: {get_value('exposure_time', 40000)}")
        self.logger.info(f"   --analogue-gain: {get_value('analogue_gain', 2.0)}")
        self.logger.info(f"   --ae-enable: {get_value('ae_enable', True)}")
        self.logger.info(f"   --af-enable: {get_value('af_enable', False)}")
        self.logger.info(f"   --lens-position: {get_value('lens_position', 0.5)}")
        
        # 🎬 СТРИМ
        self.logger.info("🎬 СТРИМ:")
        if hasattr(args, 'stream') and args.stream:
            self.logger.info(f"   --stream: {args.stream} (указано)")
        else:
            stream_enabled = getattr(settings, 'stream', None) and getattr(settings.stream, 'enabled', True)
            self.logger.info(f"   --stream: {stream_enabled} (по умолчанию)")
        
        self.logger.info(f"   --stream-width: {get_value('stream_width', 1280)}")
        self.logger.info(f"   --stream-height: {get_value('stream_height', 720)}")
        self.logger.info(f"   --stream-fps: {get_value('stream_fps', 25)}")
        
        # 📸 СЪЕМКА
        self.logger.info("📸 СЪЕМКА:")
        self.logger.info(f"   --delay: {get_value('delay', 3)}")
        self.logger.info(f"   --count: {get_value('count', 20)}")
        self.logger.info(f"   --output-dir: {get_value('output_dir', 'calibration_images')}")
        self.logger.info(f"   --max-angle: {get_value('max_angle', 45)}")
        
        # 🔧 ОТЛАДКА
        self.logger.info("🔧 ОТЛАДКА:")
        if hasattr(args, 'debug') and args.debug:
            self.logger.info(f"   --debug: {args.debug} (указано)")
        else:
            debug_enabled = getattr(settings, 'debug', None) and getattr(settings.debug, 'enabled', False)
            self.logger.info(f"   --debug: {debug_enabled} (по умолчанию)")
    
    def info(self, message: str):
        """Информационное сообщение"""
        if self.logger:
            self.logger.info(message)
    
    def warning(self, message: str):
        """Предупреждение"""
        if self.logger:
            self.logger.warning(message)
    
    def error(self, message: str):
        """Ошибка"""
        if self.logger:
            self.logger.error(message)
    
    def debug(self, message: str):
        """Отладочное сообщение"""
        if self.logger:
            self.logger.debug(message)
    
    def get_log_file_path(self) -> str:
        """Получение пути к лог-файлу"""
        return self.log_file
    
    def log_paths_info(self, settings):
        """Логирование информации о путях в выделенной секции"""
        self.logger.info("=" * 70)
        self.logger.info("📁 ПУТИ И КОНФИГУРАЦИЯ")
        self.logger.info("=" * 70)
        
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
        
        # Пути к конфигурационным файлам
        config_files = [
            '001_code/config/camera_profiles.py',
            '001_code/config/settings.py',
            '001_code/config/cli_parser.py',
            '001_code/config/file_naming.yaml'
        ]
        
        self.logger.info("📋 Конфигурационные файлы:")
        for config_file in config_files:
            full_path = os.path.join(project_root, config_file)
            if os.path.exists(full_path):
                self.logger.info(f"   ✅ {config_file}")
            else:
                self.logger.info(f"   ❌ {config_file} (не найден)")
        
        # Пути к директориям
        self.logger.info("📁 Директории:")
        self.logger.info(f"   📂 Проект: {project_root}")
        self.logger.info(f"   📂 Логи: {self.log_dir}")
        
        # Преобразуем путь к фото в абсолютный
        photo_dir = settings.capture.output_dir
        if not os.path.isabs(photo_dir):
            photo_dir = os.path.join(project_root, photo_dir)
        self.logger.info(f"   📂 Фото: {photo_dir}")
        
        # Проверка директорий
        dirs_to_check = [
            (self.log_dir, "Директория логов"),
            (photo_dir, "Директория фото")
        ]
        
        for dir_path, description in dirs_to_check:
            if os.path.exists(dir_path):
                self.logger.info(f"   ✅ {description}: {dir_path}")
            else:
                self.logger.info(f"   ❌ {description}: {dir_path} (не существует)")
        
        self.logger.info("=" * 70)

def create_logger(camera_type: str = 'unknown', log_dir: str = '002_logs') -> PicsKeeperLogger:
    """Создание экземпляра логгера"""
    return PicsKeeperLogger(camera_type, log_dir)