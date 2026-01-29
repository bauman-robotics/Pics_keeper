#!/usr/bin/env python3
"""
Модуль стрима для веб-камеры

Содержит класс WebcamStream для управления видеопотоком с веб-камеры
с поддержкой масштабирования, визуализации и интеграции с существующей архитектурой.
"""

import cv2
import time
import threading
import numpy as np
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from core.stream_settings import StreamSettings, StreamStatus, FrameInfo, StreamMetrics
from core.stream_visualization import apply_visualization_overlay
from core.stream_scaling import smart_resize
from utils.webcam_capture import WebcamCapture
from utils.logger import PicsKeeperLogger

@dataclass
class WebcamStreamConfig:
    """Конфигурация стрима веб-камеры"""
    camera_index: int = 0
    target_width: int = 1280
    target_height: int = 720
    max_fps: float = 30.0
    show_fps: bool = True
    show_status: bool = True
    show_frame_info: bool = False
    low_latency: bool = True
    enable_visualization: bool = True

class WebcamStream:
    """
    Класс для управления видеопотоком с веб-камеры
    
    Поддерживает:
    - Захват видео с веб-камеры
    - Масштабирование кадров
    - Визуализацию FPS, статуса, метрик
    - Интеграцию с системой логирования
    - Автоматическое управление ресурсами
    """
    
    def __init__(
        self, 
        config: WebcamStreamConfig,
        logger: Optional[PicsKeeperLogger] = None
    ):
        """
        Инициализация стрима веб-камеры
        
        Args:
            config: Конфигурация стрима
            logger: Система логирования
        """
        self.config = config
        self.logger = logger
        
        # Состояние стрима
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_buffer = None
        self._buffer_lock = threading.Lock()
        
        # Метрики
        self._metrics = StreamMetrics(
            total_frames=0,
            dropped_frames=0,
            avg_fps=0.0,
            min_fps=float('inf'),
            max_fps=0.0
        )
        
        self._fps_counter = 0
        self._fps_start_time = time.time()
        self._last_frame_time = 0
        
        # Обработчики
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None
        self._key_callback: Optional[Callable[[int], None]] = None
        
        # Инициализация захвата
        self._webcam = WebcamCapture(camera_type='local_web', debug=False)
        
        if self.logger:
            self.logger.info(f"WebcamStream инициализирован: {config.target_width}x{config.target_height}@{config.max_fps}fps")
    
    def start(self) -> bool:
        """
        Запуск стрима
        
        Returns:
            True, если запуск успешен
        """
        if self._running:
            if self.logger:
                self.logger.warning("WebcamStream уже запущен")
            return True
        
        try:
            # Инициализация веб-камеры
            if not self._webcam.initialize():
                if self.logger:
                    self.logger.error("Не удалось инициализировать веб-камеру")
                return False
            
            # Запуск потока захвата
            self._running = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            if self.logger:
                self.logger.info("WebcamStream запущен")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска WebcamStream: {e}")
            self._running = False
            return False
    
    def stop(self):
        """Остановка стрима"""
        if not self._running:
            return
        
        self._running = False
        
        # Ожидание завершения потока
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        
        # Освобождение ресурсов
        self._webcam.release()
        
        if self.logger:
            self.logger.info("WebcamStream остановлен")
    
    def is_running(self) -> bool:
        """Проверка, запущен ли стрим"""
        return self._running
    
    def get_status(self) -> StreamStatus:
        """
        Получение статуса стрима
        
        Returns:
            StreamStatus: Текущий статус
        """
        with self._buffer_lock:
            if self._frame_buffer is not None:
                resolution = (self._frame_buffer.shape[1], self._frame_buffer.shape[0])
            else:
                resolution = (self.config.target_width, self.config.target_height)
        
        return StreamStatus(
            fps=self._metrics.avg_fps,
            resolution=resolution,
            stream_enabled=self._running,
            low_latency=self.config.low_latency,
            timestamp=time.time()
        )
    
    def get_metrics(self) -> StreamMetrics:
        """Получение метрик производительности"""
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
    
    def _capture_loop(self):
        """Основной цикл захвата видео"""
        frame_interval = 1.0 / self.config.max_fps if self.config.max_fps > 0 else 0
        last_frame_time = time.time()
        
        while self._running:
            try:
                # Захват кадра
                frame = self._webcam.capture_frame()
                
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                current_time = time.time()
                
                # Ограничение FPS
                if frame_interval > 0:
                    time_since_last = current_time - last_frame_time
                    if time_since_last < frame_interval:
                        time.sleep(frame_interval - time_since_last)
                        continue
                
                last_frame_time = current_time
                
                # Масштабирование кадра
                if (frame.shape[1] != self.config.target_width or 
                    frame.shape[0] != self.config.target_height):
                    
                    scaled_frame = smart_resize(
                        frame,
                        self.config.target_width,
                        self.config.target_height
                    )
                else:
                    scaled_frame = frame
                
                # Обновление метрик
                self._update_metrics(current_time)
                
                # Визуализация
                if self.config.enable_visualization:
                    status = self.get_status()
                    scaled_frame = apply_visualization_overlay(
                        scaled_frame,
                        status=status,
                        show_fps=self.config.show_fps,
                        show_status=self.config.show_status,
                        show_frame_info=self.config.show_frame_info
                    )
                
                # Сохранение в буфер
                with self._buffer_lock:
                    self._frame_buffer = scaled_frame.copy()
                
                # Отображение кадра в окне OpenCV
                if self.config.show_status:
                    cv2.imshow('Webcam Stream', scaled_frame)
                
                # Вызов обработчика кадров
                if self._frame_callback:
                    try:
                        self._frame_callback(scaled_frame)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Ошибка в обработчике кадров: {e}")
                
                # Проверка нажатий клавиш
                key = cv2.waitKey(1) & 0xFF
                if key != 255 and self._key_callback:
                    try:
                        self._key_callback(key)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Ошибка в обработчике клавиш: {e}")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка в цикле захвата: {e}")
                time.sleep(0.1)
    
    def _update_metrics(self, current_time: float):
        """Обновление метрик производительности"""
        self._metrics.total_frames += 1
        self._fps_counter += 1
        
        # Расчет FPS
        if current_time - self._fps_start_time >= 1.0:
            fps = self._fps_counter / (current_time - self._fps_start_time)
            self._metrics.avg_fps = fps
            self._metrics.min_fps = min(self._metrics.min_fps, fps)
            self._metrics.max_fps = max(self._metrics.max_fps, fps)
            
            self._fps_counter = 0
            self._fps_start_time = current_time
        
        # Обновление времени последнего кадра
        self._last_frame_time = current_time
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """
        Получение текущего кадра
        
        Returns:
            Текущий кадр или None
        """
        with self._buffer_lock:
            if self._frame_buffer is not None:
                return self._frame_buffer.copy()
            return None
    
    def save_frame(self, filename: str) -> bool:
        """
        Сохранение текущего кадра
        
        Args:
            filename: Имя файла для сохранения
            
        Returns:
            True, если сохранение успешно
        """
        frame = self.get_current_frame()
        if frame is None:
            return False
        
        try:
            cv2.imwrite(filename, frame)
            if self.logger:
                self.logger.info(f"Кадр сохранен: {filename}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка сохранения кадра: {e}")
            return False
    
    def get_info(self) -> dict:
        """Получение информации о стриме"""
        status = self.get_status()
        metrics = self.get_metrics()
        
        return {
            "stream_enabled": self._running,
            "resolution": f"{status.resolution[0]}x{status.resolution[1]}",
            "fps": f"{status.fps:.1f}",
            "total_frames": metrics.total_frames,
            "avg_fps": f"{metrics.avg_fps:.1f}",
            "min_fps": f"{metrics.min_fps:.1f}",
            "max_fps": f"{metrics.max_fps:.1f}",
            "camera_index": self.config.camera_index,
            "target_resolution": f"{self.config.target_width}x{self.config.target_height}",
            "target_fps": self.config.max_fps
        }