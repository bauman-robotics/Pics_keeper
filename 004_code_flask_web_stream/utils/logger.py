#!/usr/bin/env python3
"""
Модуль логирования для Flask Webcam Stream
"""

import logging
import os
import sys
import cv2
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# Импортируем улучшенный детектор камер
from .camera_checker import CameraChecker

class StreamLogger:
    """Класс для логирования событий Flask веб-сервера"""
    
    def __init__(self, config_path: str = 'config.yaml', log_dir: str = '002_logs'):
        """
        Инициализация логгера
        
        Args:
            config_path: Путь к конфигурационному файлу
            log_dir: Директория для логов
        """
        self.config_path = config_path
        
        # Определяем базовую директорию (где находится скрипт)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        
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
        """Создание имени лог-файла с датой-временем"""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        filename = f"flask_stream_{timestamp}.log"
        self.log_file = os.path.join(self.log_dir, filename)
    
    def _setup_logger(self):
        """Настройка логгера"""
        self.logger = logging.getLogger('flask_stream')
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
        self.logger.info(f"🚀 Flask Webcam Stream запущен")
        self.logger.info(f"📁 Лог-файл: {self.log_file}")
        self.logger.info(f"⚙️  Конфигурация: {self.config_path}")
    
    def log_startup_info(self, config, camera_info=None):
        """Логирование информации о запуске"""
        self.logger.info("=" * 70)
        self.logger.info("📋 ИНФОРМАЦИЯ О ЗАПУСКЕ")
        self.logger.info("=" * 70)
        
        # Время запуска
        self.logger.info(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Параметры сервера
        self.logger.info("🌐 ПАРАМЕТРЫ СЕРВЕРА:")
        server_config = config.get('server', {})
        self.logger.info(f"   Хост: {server_config.get('host', '0.0.0.0')}")
        self.logger.info(f"   Порт: {server_config.get('port', 5000)}")
        self.logger.info(f"   Debug: {server_config.get('debug', False)}")
        self.logger.info(f"   Threaded: {server_config.get('threaded', True)}")
        
        # Параметры камеры
        self.logger.info("📷 ПАРАМЕТРЫ КАМЕРЫ:")
        camera_config = config.get('camera', {})
        self.logger.info(f"   Устройство: {camera_config.get('device', 0)}")
        self.logger.info(f"   Бэкенд: {camera_config.get('backend', 'auto')}")
        self.logger.info(f"   Разрешение: {camera_config.get('width', 'auto')}x{camera_config.get('height', 'auto')}")
        self.logger.info(f"   FPS: {camera_config.get('fps', 'auto')}")
        self.logger.info(f"   JPEG качество: {camera_config.get('jpeg_quality', 85)}")
        
        if camera_info:
            self.logger.info(f"   📸 Найденная камера: {camera_info.get('name', 'неизвестно')}")
            self.logger.info(f"   📐 Фактическое разрешение: {camera_info.get('resolution', 'неизвестно')}")
            self.logger.info(f"   📊 Фактический FPS: {camera_info.get('fps', 'неизвестно')}")
        
        # Параметры потока
        self.logger.info("🎬 ПАРАМЕТРЫ ПОТОКА:")
        stream_config = config.get('stream', {})
        self.logger.info(f"   Макс. ошибок: {stream_config.get('max_error_count', 10)}")
        self.logger.info(f"   Интервал логирования: {stream_config.get('frame_log_interval', 30)}")
        
        # Пути
        self.logger.info("📁 ПУТИ:")
        paths_config = config.get('paths', {})
        self.logger.info(f"   Шаблоны: {paths_config.get('templates_folder', 'templates')}")
        self.logger.info(f"   Логи: {self.log_dir}")
        
        self.logger.info("=" * 70)
    
    def log_camera_test(self, backend_name, success, resolution=None, fps=None, error=None):
        """Логирование тестирования камеры"""
        if success:
            self.logger.info(f"✅ {backend_name} РАБОТАЕТ!")
            if resolution:
                self.logger.info(f"   Разрешение: {resolution}")
            if fps:
                self.logger.info(f"   FPS: {fps}")
        else:
            self.logger.warning(f"❌ {backend_name} не работает: {error}")
    
    def log_stream_start(self):
        """Логирование запуска стрима"""
        self.logger.info("🎬 Стрим запущен")
    
    def log_stream_stop(self):
        """Логирование остановки стрима"""
        self.logger.info("🎬 Стрим остановлен")
    
    def log_frame_sent(self, frame_count):
        """Логирование отправки кадра"""
        if frame_count % 30 == 0:
            self.logger.info(f"📊 Отправлено кадров: {frame_count}")
    
    def log_error(self, message):
        """Логирование ошибки"""
        self.logger.error(message)
    
    def log_info(self, message):
        """Информационное сообщение"""
        self.logger.info(message)
    
    def log_warning(self, message):
        """Предупреждение"""
        self.logger.warning(message)
    
    def get_log_file_path(self) -> str:
        """Получение пути к лог-файлу"""
        return self.log_file
    
    def scan_available_cameras(self, max_devices: int = 10) -> List[Dict]:
        """Сканирование доступных камер и их параметров с использованием v4l2-ctl"""
        # Создаем улучшенный детектор камер
        checker = CameraChecker()
        
        # Детектируем камеры
        cameras = checker.detect_cameras(max_devices)
        
        # Логируем результаты
        checker.log_detection_results(cameras)
        
        return cameras

def create_logger(config_path: str = 'config.yaml', log_dir: str = '002_logs') -> StreamLogger:
    """Создание экземпляра логгера"""
    return StreamLogger(config_path, log_dir)