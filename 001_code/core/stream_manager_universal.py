#!/usr/bin/env python3
"""
Универсальный менеджер стрима

Содержит класс UniversalStreamManager для управления видеопотоком
с поддержкой различных типов камер (IMX708, IMX415, OV5647, веб-камера).
"""

import cv2
import time
import threading
import numpy as np
from typing import Optional, Callable, Union, Dict, Any
from dataclasses import dataclass, asdict
from core.stream_manager import StreamManager, StreamFrame
from core.webcam_stream import WebcamStream, WebcamStreamConfig
from core.stream_settings import StreamSettings, StreamStatus, FrameInfo, StreamMetrics
from core.stream_visualization import apply_visualization_overlay
from core.stream_scaling import smart_resize
from core.stream_server import StreamServer, StreamServerConfig
from utils.logger import PicsKeeperLogger
from utils.file_namer import FileNamer

@dataclass
class UniversalStreamConfig:
    """Конфигурация универсального стрима"""
    camera_type: str = "local_web"
    camera_index: int = 0
    target_width: int = 1280
    target_height: int = 720
    max_fps: float = 30.0
    show_fps: bool = True
    show_status: bool = True
    show_frame_info: bool = False
    low_latency: bool = True
    enable_visualization: bool = True
    enable_capture: bool = True
    capture_dir: str = "./003_pics"
    file_prefix: str = "chessboard"
    stream_port: int = 8080
    web_interface: bool = True
    stream_analysis: bool = False
    stream_quality: int = 50

class UniversalStreamManager:
    """
    Универсальный менеджер видеопотока
    
    Поддерживает различные типы камер:
    - IMX708, IMX415, OV5647 (через picamera2)
    - Веб-камеры (через OpenCV)
    
    Предоставляет единый интерфейс для управления стримом.
    """
    
    def __init__(
        self, 
        config: UniversalStreamConfig,
        logger: Optional[PicsKeeperLogger] = None
    ):
        """
        Инициализация универсального менеджера стрима
        
        Args:
            config: Конфигурация стрима
            logger: Система логирования
        """
        self.config = config
        self.logger = logger
        
        # Текущий тип камеры
        self._camera_type = config.camera_type
        
        # Менеджеры для разных типов камер
        self._picamera_manager: Optional[StreamManager] = None
        self._webcam_stream: Optional[WebcamStream] = None
        
        # Веб-сервер для MJPEG стрима
        self._stream_server: Optional[StreamServer] = None
        self._server_thread: Optional[threading.Thread] = None
        
        # Состояние
        self._running = False
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        
        # Обработчики
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None
        self._key_callback: Optional[Callable[[int], None]] = None
        
        # Система именования файлов
        self._file_namer = FileNamer()
        
        # Метрики
        self._metrics = StreamMetrics(
            total_frames=0,
            dropped_frames=0,
            avg_fps=0.0,
            min_fps=float('inf'),
            max_fps=0.0
        )
        
        if self.logger:
            self.logger.info(f"UniversalStreamManager инициализирован для камеры: {self._camera_type}")
    
    def start(self) -> bool:
        """
        Запуск стрима
        
        Returns:
            True, если запуск успешен
        """
        if self._running:
            if self.logger:
                self.logger.warning("UniversalStreamManager уже запущен")
            return True
        
        try:
            if self._camera_type in ['imx708', 'imx708_wide', 'imx415', 'ov5647']:
                return self._start_picamera_stream()
            elif self._camera_type == 'local_web':
                return self._start_webcam_stream()
            else:
                if self.logger:
                    self.logger.error(f"Неподдерживаемый тип камеры: {self._camera_type}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска UniversalStreamManager: {e}")
            self._running = False
            return False
    
    def start_web_server(self) -> bool:
        """
        Запуск веб-сервера для MJPEG стрима
        
        Returns:
            True, если запуск успешен
        """
        if not self.config.web_interface:
            if self.logger:
                self.logger.info("Веб-интерфейс отключен")
            return True
        
        try:
            # Создаем конфигурацию для веб-сервера
            server_config = StreamServerConfig(
                port=self.config.stream_port,
                stream_width=self.config.target_width,
                stream_height=self.config.target_height,
                stream_fps=self.config.max_fps,
                stream_quality=self.config.stream_quality,
                stream_analysis=self.config.stream_analysis,
                low_latency=self.config.low_latency,
                camera_name=self._camera_type,
                save_dir=self.config.capture_dir,
                jpeg_quality=self.config.stream_quality,
                max_angle=45.0,
                warn_angle=30.0,
                force_capture=False
            )
            
            # Создаем веб-сервер
            self._stream_server = StreamServer(
                config=server_config,
                frame_source=self.get_current_frame,
                logger=self.logger
            )
            
            # Запускаем сервер в отдельном потоке
            self._server_thread = self._stream_server.start_server()
            
            if self.logger:
                self.logger.info(f"Веб-сервер запущен на порту {self.config.stream_port}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска веб-сервера: {e}")
            return False
    
    def stop_web_server(self):
        """Остановка веб-сервера"""
        if self._stream_server:
            self._stream_server.stop_server()
            self._stream_server = None
            self._server_thread = None
            if self.logger:
                self.logger.info("Веб-сервер остановлен")
    
    def stop(self):
        """Остановка стрима"""
        if not self._running:
            return
        
        self._running = False
        
        if self._picamera_manager:
            self._picamera_manager.stop()
        
        if self._webcam_stream:
            self._webcam_stream.stop()
        
        if self.logger:
            self.logger.info("UniversalStreamManager остановлен")
    
    def is_running(self) -> bool:
        """Проверка, запущен ли стрим"""
        return self._running
    
    def get_status(self) -> StreamStatus:
        """
        Получение статуса стрима
        
        Returns:
            StreamStatus: Текущий статус
        """
        if self._picamera_manager and self._picamera_manager.is_running():
            return self._picamera_manager.get_status()
        elif self._webcam_stream and self._webcam_stream.is_running():
            return self._webcam_stream.get_status()
        else:
            return StreamStatus(
                fps=0.0,
                resolution=(self.config.target_width, self.config.target_height),
                stream_enabled=self._running,
                low_latency=self.config.low_latency,
                timestamp=time.time()
            )
    
    def get_metrics(self) -> StreamMetrics:
        """Получение метрик производительности"""
        if self._picamera_manager and self._picamera_manager.is_running():
            return self._picamera_manager.get_metrics()
        elif self._webcam_stream and self._webcam_stream.is_running():
            return self._webcam_stream.get_metrics()
        else:
            return self._metrics
    
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """
        Установка обработчика кадров
        
        Args:
            callback: Функция для обработки кадров
        """
        self._frame_callback = callback
    
    def set_key_callback(self, callback: Callable[[int], None]):
        """
        Установка обработчика нажатий клавиш
        
        Args:
            callback: Функция для обработки нажатий клавиш
        """
        self._key_callback = callback
    
    def capture_photo(self, filename: Optional[str] = None) -> bool:
        """
        Сделать снимок
        
        Args:
            filename: Имя файла для сохранения (если None, будет сгенерировано автоматически)
            
        Returns:
            True, если снимок сделан успешно
        """
        try:
            # Получаем текущий кадр
            frame = self.get_current_frame()
            if frame is None:
                if self.logger:
                    self.logger.warning("Нет доступного кадра для съемки")
                return False
            
            # Генерируем имя файла, если не указано
            if filename is None:
                filename = self._file_namer.generate_filename(
                    prefix=self.config.file_prefix,
                    camera=self._camera_type,
                    extension="jpg"
                )
            
            # Сохраняем изображение
            cv2.imwrite(filename, frame)
            
            if self.logger:
                self.logger.info(f"Фото сохранено: {filename}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка при съемке: {e}")
            return False
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """
        Получение текущего кадра
        
        Returns:
            Текущий кадр или None
        """
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None
    
    def switch_camera(self, camera_type: str) -> bool:
        """
        Переключение типа камеры
        
        Args:
            camera_type: Новый тип камеры
            
        Returns:
            True, если переключение успешно
        """
        if self._camera_type == camera_type:
            return True
        
        # Останавливаем текущий стрим
        self.stop()
        
        # Меняем тип камеры
        self._camera_type = camera_type
        
        # Запускаем новый стрим
        return self.start()
    
    def get_info(self) -> Dict[str, Any]:
        """Получение информации о стриме"""
        status = self.get_status()
        metrics = self.get_metrics()
        
        info = {
            "camera_type": self._camera_type,
            "stream_enabled": self._running,
            "resolution": f"{status.resolution[0]}x{status.resolution[1]}",
            "fps": f"{status.fps:.1f}",
            "total_frames": metrics.total_frames,
            "avg_fps": f"{metrics.avg_fps:.1f}",
            "min_fps": f"{metrics.min_fps:.1f}",
            "max_fps": f"{metrics.max_fps:.1f}",
            "target_resolution": f"{self.config.target_width}x{self.config.target_height}",
            "target_fps": self.config.max_fps,
            "supports_capture": self.config.enable_capture,
            "capture_dir": self.config.capture_dir
        }
        
        # Добавляем информацию о конкретном менеджере
        if self._picamera_manager:
            info["manager_type"] = "picamera"
            info["manager_info"] = self._picamera_manager.get_info()
        elif self._webcam_stream:
            info["manager_type"] = "webcam"
            info["manager_info"] = self._webcam_stream.get_info()
        
        return info
    
    def _start_picamera_stream(self) -> bool:
        """Запуск стрима для picamera"""
        try:
            # Создаем настройки для StreamManager
            stream_settings = StreamSettings(
                enabled=True,
                target_width=self.config.target_width,
                target_height=self.config.target_height,
                max_fps=self.config.max_fps,
                low_latency=self.config.low_latency,
                show_fps=self.config.show_fps,
                show_status=self.config.show_status,
                show_frame_info=self.config.show_frame_info
            )
            
            # Создаем менеджер
            self._picamera_manager = StreamManager(
                settings=stream_settings,
                camera_settings={'type': self._camera_type},
                logger=self.logger
            )
            
            # Устанавливаем обработчики
            self._picamera_manager.set_frame_callback(self._on_frame_received)
            self._picamera_manager.set_key_callback(self._on_key_pressed)
            
            # Запускаем
            success = self._picamera_manager.start()
            if success:
                self._running = True
                if self.logger:
                    self.logger.info(f"StreamManager для {self._camera_type} запущен")
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска StreamManager: {e}")
            return False
    
    def _start_webcam_stream(self) -> bool:
        """Запуск стрима для веб-камеры"""
        try:
            # Создаем конфигурацию для WebcamStream
            webcam_config = WebcamStreamConfig(
                camera_index=self.config.camera_index,
                target_width=self.config.target_width,
                target_height=self.config.target_height,
                max_fps=self.config.max_fps,
                show_fps=self.config.show_fps,
                show_status=self.config.show_status,
                show_frame_info=self.config.show_frame_info,
                low_latency=self.config.low_latency,
                enable_visualization=self.config.enable_visualization
            )
            
            # Создаем стрим
            self._webcam_stream = WebcamStream(
                config=webcam_config,
                logger=self.logger
            )
            
            # Устанавливаем обработчики
            self._webcam_stream.set_frame_callback(self._on_frame_received)
            self._webcam_stream.set_key_callback(self._on_key_pressed)
            
            # Запускаем
            success = self._webcam_stream.start()
            if success:
                self._running = True
                if self.logger:
                    self.logger.info("WebcamStream запущен")
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска WebcamStream: {e}")
            return False
    
    def _on_frame_received(self, frame: np.ndarray):
        """Обработчик получения кадра"""
        with self._frame_lock:
            self._current_frame = frame.copy()
        
        # Вызываем пользовательский обработчик
        if self._frame_callback:
            try:
                self._frame_callback(frame)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка в обработчике кадров: {e}")
    
    def _on_key_pressed(self, key: int):
        """Обработчик нажатий клавиш"""
        # Обрабатываем съемку по нажатию клавиши
        if key == ord('s') and self.config.enable_capture:
            self.capture_photo()
        
        # Вызываем пользовательский обработчик
        if self._key_callback:
            try:
                self._key_callback(key)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка в обработчике клавиш: {e}")
    
    def __enter__(self):
        """Контекстный менеджер - запуск"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - остановка"""
        self.stop()