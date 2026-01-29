#!/usr/bin/env python3
"""
Модуль управления стримом с масштабированием

Содержит основной класс StreamManager для управления видеопотоком,
функции визуализации и масштабирования изображения.
"""

import time
import threading
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, Deque
from collections import deque
from core.stream_settings import StreamSettings, StreamStatus, FrameInfo, StreamMetrics
from core.stream_visualization import draw_fps_counter, draw_status_overlay, draw_frame_info
from core.stream_scaling import scale_frame_to_target_resolution, calculate_target_resolution

@dataclass
class StreamFrame:
    """Класс для хранения кадра со метаданными"""
    frame: np.ndarray
    timestamp: float
    processing_time: float
    frame_info: FrameInfo

class StreamManager:
    """Класс управления видеопотоком с масштабированием"""
    
    def __init__(self, settings: StreamSettings, camera_settings: dict):
        """
        Инициализация StreamManager
        
        Args:
            settings: Настройки стрима
            camera_settings: Настройки камеры
        """
        self.settings = settings
        self.camera_settings = camera_settings
        
        # Состояние стрима
        self._running = False
        self._stream_thread = None
        self._frame_buffer = deque(maxlen=3)
        self._frame_lock = threading.Lock()
        
        # Метрики
        self._metrics = StreamMetrics(
            total_frames=0,
            dropped_frames=0,
            avg_fps=0.0,
            min_fps=float('inf'),
            max_fps=0.0
        )
        
        # Технические параметры
        self._last_frame_time = 0
        self._frame_count = 0
        self._total_latency = 0
        
        # Инициализация OpenCV окна
        if self.settings.show_status:
            cv2.namedWindow('Stream', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Stream', settings.target_width, settings.target_height)
    
    def start_stream(self) -> None:
        """Запуск видеопотока"""
        if self._running:
            print("⚠️ Стрим уже запущен")
            return
        
        self._running = True
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        print(f"✅ Стрим запущен: {self.settings.target_width}x{self.settings.target_height} @ {self.settings.max_fps} FPS")
    
    def stop_stream(self) -> None:
        """Остановка видеопотока"""
        if not self._running:
            return
        
        self._running = False
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=1.0)
        
        # Закрываем окно OpenCV
        if self.settings.show_status:
            cv2.destroyAllWindows()
        
        print("✅ Стрим остановлен")
    
    def is_running(self) -> bool:
        """Проверка, запущен ли стрим"""
        return self._running
    
    def get_fps(self) -> float:
        """Получение текущего FPS"""
        return self._metrics.avg_fps
    
    def get_status(self) -> StreamStatus:
        """Получение статуса стрима"""
        return StreamStatus(
            fps=self._metrics.avg_fps,
            resolution=(self.settings.target_width, self.settings.target_height),
            stream_enabled=self._running,
            low_latency=self.settings.low_latency,
            timestamp=time.time()
        )
    
    def get_metrics(self) -> StreamMetrics:
        """Получение метрик производительности"""
        return self._metrics
    
    def _stream_loop(self) -> None:
        """Основной цикл стрима"""
        frame_count = 0
        last_stats_time = time.time()
        last_frame_time = time.time()
        
        while self._running:
            try:
                # Контроль FPS
                current_time = time.time()
                if current_time - last_frame_time < 1.0 / self.settings.max_fps:
                    time.sleep(0.001)
                    continue
                
                # Получаем кадр от камеры (заглушка)
                frame = self._capture_frame()
                
                if frame is not None and frame.size > 0:
                    # Обработка кадра
                    processed_frame = self._process_frame(frame)
                    
                    # Сохраняем кадр в буфер
                    with self._frame_lock:
                        self._frame_buffer.append(processed_frame)
                    
                    # Обновление метрик
                    frame_count += 1
                    current_time = time.time()
                    frame_latency = current_time - last_frame_time
                    self._total_latency += frame_latency
                    last_frame_time = current_time
                    
                    # Статистика каждые 5 секунд
                    if current_time - last_stats_time >= 5:
                        self._update_metrics(frame_count, self._total_latency)
                        frame_count = 0
                        self._total_latency = 0
                        last_stats_time = current_time
                
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f"❌ Ошибка в цикле стрима: {e}")
                time.sleep(0.1)
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        """
        Захват кадра от камеры
        
        В реальной реализации будет использовать picamera2 или веб-камеру
        """
        try:
            # Имитация захвата кадра
            # В реальной реализации: frame = self.picam2.capture_array()
            
            # Для тестирования создаем тестовое изображение
            if hasattr(self, '_test_frame') and self._test_frame is not None:
                return self._test_frame
            
            # Создаем тестовое изображение
            height, width = 1080, 1920
            frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            
            # Добавляем текст для тестирования
            cv2.putText(frame, "Test Stream Frame", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            self._test_frame = frame
            return frame
            
        except Exception as e:
            print(f"⚠️ Ошибка захвата кадра: {e}")
            return None
    
    def _process_frame(self, frame: np.ndarray) -> StreamFrame:
        """
        Обработка кадра: масштабирование и визуализация
        
        Args:
            frame: Исходный кадр
            
        Returns:
            StreamFrame: Обработанный кадр с метаданными
        """
        start_time = time.time()
        
        # 1. Масштабирование до целевого разрешения
        if (frame.shape[1], frame.shape[0]) != (self.settings.target_width, self.settings.target_height):
            frame = scale_frame_to_target_resolution(
                frame, 
                self.settings.target_width, 
                self.settings.target_height
            )
        
        # 2. Конвертация формата (если нужно)
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # RGB -> BGR для OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif len(frame.shape) == 2:
            # Монохром -> Цветной
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        
        # 3. Визуализация (если включена)
        if self.settings.show_fps:
            frame = draw_fps_counter(frame, self._metrics.avg_fps)
        
        if self.settings.show_status:
            status = self.get_status()
            frame = draw_status_overlay(frame, status)
        
        if self.settings.show_frame_info:
            frame_info = FrameInfo(
                width=frame.shape[1],
                height=frame.shape[0],
                channels=frame.shape[2] if len(frame.shape) == 3 else 1,
                timestamp=time.time(),
                processing_time=time.time() - start_time
            )
            frame = draw_frame_info(frame, frame_info)
        
        # 4. Отображение в окне (если включено)
        if self.settings.show_status:
            cv2.imshow('Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self._running = False
        
        # 5. Создаем метаданные
        frame_info = FrameInfo(
            width=frame.shape[1],
            height=frame.shape[0],
            channels=frame.shape[2] if len(frame.shape) == 3 else 1,
            timestamp=time.time(),
            processing_time=time.time() - start_time
        )
        
        return StreamFrame(
            frame=frame,
            timestamp=time.time(),
            processing_time=time.time() - start_time,
            frame_info=frame_info
        )
    
    def _update_metrics(self, frame_count: int, total_latency: float) -> None:
        """Обновление метрик производительности"""
        if frame_count > 0:
            avg_latency = total_latency / frame_count
            fps = frame_count / 5
            
            # Обновляем метрики
            self._metrics.total_frames += frame_count
            self._metrics.avg_fps = fps
            self._metrics.min_fps = min(self._metrics.min_fps, fps)
            self._metrics.max_fps = max(self._metrics.max_fps, fps)
            
            # Логирование (если включен debug)
            if hasattr(self, 'debug') and self.debug:
                print(f"📊 Стрим: {fps:.1f} FPS, Задержка: {avg_latency*1000:.0f} мс")
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Получение последнего кадра"""
        with self._frame_lock:
            if self._frame_buffer:
                return self._frame_buffer[-1].frame
            return None
    
    def get_latest_frame_with_info(self) -> Optional[StreamFrame]:
        """Получение последнего кадра с метаданными"""
        with self._frame_lock:
            if self._frame_buffer:
                return self._frame_buffer[-1]
            return None
    
    def cleanup(self) -> None:
        """Очистка ресурсов"""
        self.stop_stream()
        if hasattr(self, '_test_frame'):
            delattr(self, '_test_frame')
        print("🧹 StreamManager очищен")


# Вспомогательные функции

def create_stream_window(title: str, width: int, height: int) -> None:
    """Создание окна для стрима"""
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, width, height)

def update_stream_window(frame: np.ndarray, title: str = 'Stream') -> None:
    """Обновление окна стрима"""
    cv2.imshow(title, frame)

def cleanup_stream_resources() -> None:
    """Очистка ресурсов OpenCV"""
    cv2.destroyAllWindows()

def get_stream_info() -> dict:
    """Получение информации о возможностях стрима"""
    return {
        "opencv_version": cv2.__version__,
        "supported_formats": ["RGB", "BGR", "GRAY"],
        "max_resolution": "3840x2160",
        "recommended_fps": "30-60",
        "low_latency_modes": ["INTER_AREA", "INTER_LINEAR"]
    }