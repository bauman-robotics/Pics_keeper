#!/usr/bin/env python3

# logger.py 
"""
Модуль логирования для Flask Webcam Stream
"""

import logging
import os
import sys
#import cv2
from datetime import datetime
# from pathlib import Path
# from typing import Optional, List, Dict

class StreamLogger:
    """Класс для логирования событий Flask веб-сервера"""
    
    def __init__(self, config_path: str = 'config_rpi.yaml', log_dir: str = '002_logs'):
        """
        Инициализация логгера
        
        Args:
            config_path: Путь к конфигурационному файлу
            log_dir: Директория для логов
        """
        self.config_path = config_path
        
        # Определяем базовую директорию (где находится скрипт)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # os.path.dirname(path) возвращает родительскую директорию переданного пути
        project_root = os.path.dirname(os.path.dirname(script_dir))
        '''
        # Пример пути
        path = "/home/user/project/src/main.py"

        # Каждый вызов dirname "поднимается" на уровень выше
        print(os.path.dirname(path))         # /home/user/project/src
        print(os.path.dirname(os.path.dirname(path)))  # /home/user/project
        print(os.path.dirname(os.path.dirname(os.path.dirname(path))))  # /home/user        
        '''
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
    
    # def log_startup_info(self, config, camera_info=None):
    #     """Логирование информации о запуске"""
    #     self.logger.info("=" * 70)
    #     self.logger.info("📋 ИНФОРМАЦИЯ О ЗАПУСКЕ")
    #     self.logger.info("=" * 70)
        
    #     # Время запуска
    #     self.logger.info(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    #     # Параметры сервера
    #     self.logger.info("🌐 ПАРАМЕТРЫ СЕРВЕРА:")
    #     server_config = config.get('server', {})
    #     self.logger.info(f"   Хост: {server_config.get('host', '0.0.0.0')}")
    #     self.logger.info(f"   Порт: {server_config.get('port', 5000)}")
    #     self.logger.info(f"   Debug: {server_config.get('debug', False)}")
    #     self.logger.info(f"   Threaded: {server_config.get('threaded', True)}")
        
    #     # Параметры камеры
    #     self.logger.info("📷 ПАРАМЕТРЫ КАМЕРЫ:")
    #     camera_config = config.get('camera', {})
    #     self.logger.info(f"   Устройство: {camera_config.get('device', 0)}")
    #     self.logger.info(f"   Бэкенд: {camera_config.get('backend', 'auto')}")
    #     self.logger.info(f"   Разрешение: {camera_config.get('width', 'auto')}x{camera_config.get('height', 'auto')}")
    #     self.logger.info(f"   FPS: {camera_config.get('fps', 'auto')}")
    #     self.logger.info(f"   JPEG качество: {camera_config.get('jpeg_quality', 85)}")
        
    #     if camera_info:
    #         self.logger.info(f"   📸 Найденная камера: {camera_info.get('name', 'неизвестно')}")
    #         self.logger.info(f"   📐 Фактическое разрешение: {camera_info.get('resolution', 'неизвестно')}")
    #         self.logger.info(f"   📊 Фактический FPS: {camera_info.get('fps', 'неизвестно')}")
        
    #     # Параметры потока
    #     self.logger.info("🎬 ПАРАМЕТРЫ ПОТОКА:")
    #     stream_config = config.get('stream', {})
    #     self.logger.info(f"   Макс. ошибок: {stream_config.get('max_error_count', 10)}")
    #     self.logger.info(f"   Интервал логирования: {stream_config.get('frame_log_interval', 30)}")
        
    #     # Пути
    #     self.logger.info("📁 ПУТИ:")
    #     paths_config = config.get('paths', {})
    #     self.logger.info(f"   Шаблоны: {paths_config.get('templates_folder', 'templates')}")
    #     self.logger.info(f"   Логи: {self.log_dir}")
        
    #     self.logger.info("=" * 70)
    
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
        self.logger.info(f"   Max concurrent streams: {server_config.get('max_concurrent_streams', 4)}")
        
        # Параметры камеры
        self.logger.info("📷 ПАРАМЕТРЫ КАМЕРЫ:")
        camera_config = config.get('camera', {})
        device = camera_config.get('device', 0)
        self.logger.info(f"   Устройство: {device}")
        self.logger.info(f"   Тип камеры: {camera_config.get('type', 'auto')}")
        self.logger.info(f"   Бэкенд: {camera_config.get('backend', 'auto')}")
        self.logger.info(f"   Разрешение: {camera_config.get('width', 'auto')}x{camera_config.get('height', 'auto')}")
        self.logger.info(f"   FPS: {camera_config.get('fps', 'auto')}")
        self.logger.info(f"   JPEG качество: {camera_config.get('jpeg_quality', 85)}")
        
        # ===== НОВЫЕ ПАРАМЕТРЫ ДЛЯ USB КАМЕР =====
        if 'fourcc' in camera_config:
            self.logger.info(f"   📼 FOURCC кодек: {camera_config.get('fourcc', 'MJPG')}")
        if 'auto_exposure' in camera_config:
            self.logger.info(f"   ⚡ Автоэкспозиция: {camera_config.get('auto_exposure', 0.25)}")
        
        # ===== НАСТРОЙКИ ДЛЯ CSI КАМЕР =====
        if str(device).startswith('csi_'):
            camera_idx = device.split('_')[1] if '_' in device else '0'
            camera_key = f"csi_{camera_idx}"
            
            # Получаем настройки для конкретной CSI камеры
            csi_config = config.get('csi_cameras', {}).get(camera_key, {})
            
            self.logger.info(f"\n   🔧 СПЕЦИАЛЬНЫЕ НАСТРОЙКИ ДЛЯ {camera_key}:")
            self.logger.info(f"      Модель: {csi_config.get('name', 'Unknown')}")
            
            # Основные параметры
            if 'sensor_mode' in csi_config:
                self.logger.info(f"      Режим сенсора: {csi_config.get('sensor_mode', 0)}")
            if 'fps_limit' in csi_config:
                self.logger.info(f"      Лимит FPS: {csi_config.get('fps_limit', 30)}")
            
            # Параметры экспозиции
            self.logger.info(f"      ⚡ Режим экспозиции: {csi_config.get('ae_mode', 'auto')}")
            if csi_config.get('ae_mode') == 'manual':
                self.logger.info(f"         Выдержка: {csi_config.get('exposure_time', 10000)} мкс")
                self.logger.info(f"         Gain: {csi_config.get('analogue_gain', 1.0)}")
            if 'ae_metering_mode' in csi_config:
                self.logger.info(f"      📊 Метринг экспозиции: {csi_config.get('ae_metering_mode', 'centre')}")
            
            # Параметры баланса белого
            self.logger.info(f"      🎨 Баланс белого: {csi_config.get('awb_mode', 'auto')}")
            
            # ===== ПАРАМЕТРЫ ДЛЯ IMX708 (с автофокусом) =====
            if camera_key == 'csi_0':
                self.logger.info(f"      🔍 АВТОФОКУС (IMX708):")
                self.logger.info(f"         Режим: {csi_config.get('af_mode', 'continuous')}")
                if csi_config.get('af_mode') == 'manual':
                    self.logger.info(f"         Позиция линзы: {csi_config.get('lens_position', 0.0)}")
                if csi_config.get('af_window', False):
                    self.logger.info(f"         Окно фокуса: {csi_config.get('af_window_size', 0.3)*100}% кадра")
                
                # HDR для IMX708
                if csi_config.get('hdr_mode', False):
                    self.logger.info(f"      🌈 HDR: {csi_config.get('hdr_type', 'multi')}")
            
            # ===== ПАРАМЕТРЫ ДЛЯ IMX415 (роллинг-затвор) =====
            elif camera_key == 'csi_1':
                self.logger.info(f"      📸 Тип затвора: rolling")
                if csi_config.get('hdr_mode', False):
                    self.logger.info(f"      🌈 HDR: {csi_config.get('hdr_type', 'multi')}")
            
            # Дополнительные настройки изображения
            self.logger.info(f"      ✨ Настройки изображения:")
            self.logger.info(f"         Яркость: {csi_config.get('brightness', 0.0)}")
            self.logger.info(f"         Контраст: {csi_config.get('contrast', 1.0)}")
            self.logger.info(f"         Насыщенность: {csi_config.get('saturation', 1.0)}")
            self.logger.info(f"         Резкость: {csi_config.get('sharpness', 1.0)}")
            
            if 'noise_reduction' in csi_config:
                self.logger.info(f"      🔇 Шумоподавление: {csi_config.get('noise_reduction', 'fast')}")
        
        # Информация о найденной камере
        if camera_info:
            self.logger.info(f"\n   📸 Найденная камера: {camera_info.get('name', 'неизвестно')}")
            self.logger.info(f"   📐 Фактическое разрешение: {camera_info.get('resolution', 'неизвестно')}")
            self.logger.info(f"   📊 Фактический FPS: {camera_info.get('fps', 'неизвестно')}")
        
        # Параметры потока
        self.logger.info("\n🎬 ПАРАМЕТРЫ ПОТОКА:")
        stream_config = config.get('stream', {})
        self.logger.info(f"   Макс. ошибок: {stream_config.get('max_error_count', 10)}")
        self.logger.info(f"   Интервал логирования: {stream_config.get('frame_log_interval', 30)}")
        self.logger.info(f"   Размер буфера: {stream_config.get('buffer_size', 30)}")
        self.logger.info(f"   Автостарт: {stream_config.get('auto_start', True)}")
        
        # Пути
        self.logger.info("📁 ПУТИ:")
        paths_config = config.get('paths', {})
        self.logger.info(f"   Шаблоны: {paths_config.get('templates_folder', 'templates')}")
        self.logger.info(f"   Логи: {self.log_dir}")
        self.logger.info(f"   Фото: {paths_config.get('photos_folder', 'static/photos')}")
        
        # Интервалы
        self.logger.info("⏱️  ИНТЕРВАЛЫ:")
        intervals_config = config.get('intervals', {})
        self.logger.info(f"   Обновление статуса: {intervals_config.get('status_update', 2000)} мс")
        self.logger.info(f"   Задержка при ошибке: {intervals_config.get('error_retry_delay', 1000)} мс")
        
        # Дополнительные настройки
        self.logger.info("⚙️  ДОПОЛНИТЕЛЬНО:")
        advanced_config = config.get('advanced', {})
        self.logger.info(f"   Авторестарт: {advanced_config.get('auto_restart', True)}")
        self.logger.info(f"   Подробное логирование: {advanced_config.get('verbose_logging', True)}")
        self.logger.info(f"   Метрики: {advanced_config.get('enable_metrics', True)}")
        
        self.logger.info("=" * 70)


    # Методы для внутреннего логгера
    def info(self, message):
        """Информационное сообщение"""
        self.logger.info(message)
    
    def error(self, message):
        """Логирование ошибки"""
        self.logger.error(message)
    
    def warning(self, message):
        """Предупреждение"""
        self.logger.warning(message)
    
    def debug(self, message):
        """Отладочное сообщение"""
        self.logger.debug(message)
    
    # Алиасы для обратной совместимости
    def log_info(self, message):
        """Алиас для info()"""
        self.info(message)
    
    def log_error(self, message):
        """Алиас для error()"""
        self.error(message)
    
    def log_warning(self, message):
        """Алиас для warning()"""
        self.warning(message)
    
    def log_debug(self, message):
        """Алиас для debug()"""
        self.debug(message)

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


    def log_web_action(self, action: str, status: str, details: str = "", 
                       user_ip: str = None, user_agent: str = None):
        """
        Логирование действий на веб-странице
        
        Args:
            action: Действие (start_stream, stop_stream, select_camera, etc.)
            status: Статус (success, error, warning)
            details: Детали действия
            user_ip: IP адрес пользователя (опционально)
            user_agent: User Agent браузера (опционально)
        """
        log_message = f"🌐 Веб-действие: {action} | Статус: {status}"
        
        if details:
            log_message += f" | Детали: {details}"
        if user_ip:
            log_message += f" | IP: {user_ip}"
        if user_agent:
            # Обрезаем длинные user agent строки
            short_agent = user_agent[:100] + "..." if len(user_agent) > 100 else user_agent
            log_message += f" | User-Agent: {short_agent}"
        
        # Логируем в зависимости от статуса
        if status == 'error':
            self.logger.error(log_message)
        elif status == 'warning':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_button_click(self, button_name: str, page: str = "", 
                         user_ip: str = None, additional_info: dict = None):
        """
        Логирование нажатий на кнопки
        
        Args:
            button_name: Название кнопки
            page: Страница, на которой была нажата кнопка
            user_ip: IP адрес пользователя
            additional_info: Дополнительная информация (например, параметры запроса)
        """
        log_message = f"🖱️ Нажатие кнопки: '{button_name}'"
        
        if page:
            log_message += f" | Страница: {page}"
        if user_ip:
            log_message += f" | IP: {user_ip}"
        
        self.logger.info(log_message)
        
        # Логируем дополнительную информацию если есть
        if additional_info:
            for key, value in additional_info.items():
                if key not in ['password', 'token', 'secret']:  # Не логируем чувствительные данные
                    self.logger.debug(f"   📋 {key}: {value}")
    

    def get_logs(self, limit: int = 100):
        """
        Получение последних записей из лог-файла        
        Args:
            limit: Максимальное количество записей для возврата            
        Returns:
            Список словарей с логами
        """
        try:
            logs = []
            
            # Читаем текущий лог-файл
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Парсим логи
                for line in lines[-limit:]:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Определяем уровень логирования
                    log_level = 'info'
                    if ' - ERROR - ' in line:
                        log_level = 'error'
                    elif ' - WARNING - ' in line:
                        log_level = 'warning'
                    elif ' - DEBUG - ' in line:
                        log_level = 'debug'
                    elif ' - CRITICAL - ' in line:
                        log_level = 'critical'
                    
                    logs.append({
                        'raw': line,
                        'type': log_level,
                        'message': line,
                        'timestamp': line.split(' - ')[0] if ' - ' in line else ''
                    })
            
            return logs
            
        except Exception as e:
            self.logger.error(f"Ошибка чтения логов: {e}")
            return []


def create_logger(config_path: str = 'config_rpi.yaml', log_dir: str = '002_logs') -> StreamLogger:
    """Создание экземпляра логгера"""
    return StreamLogger(config_path, log_dir)