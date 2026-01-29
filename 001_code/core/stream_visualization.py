#!/usr/bin/env python3
"""
Модуль визуализации для стрима

Содержит функции для отрисовки различных элементов на кадрах стрима:
FPS, статус, информацию о кадре, метрики и т.д.
"""

import cv2
import time
import numpy as np
from typing import Tuple, Optional
from core.stream_settings import StreamStatus, FrameInfo, StreamMetrics

def draw_fps_counter(frame: np.ndarray, fps: float) -> np.ndarray:
    """
    Отрисовка счетчика FPS на кадре
    
    Args:
        frame: Исходный кадр
        fps: Текущий FPS
        
    Returns:
        Кадр с отрисованным FPS
    """
    if fps <= 0:
        return frame
    
    # Определяем цвет в зависимости от FPS
    if fps >= 25:
        color = (0, 255, 0)  # Зеленый - хороший FPS
    elif fps >= 15:
        color = (0, 255, 255)  # Желтый - средний FPS
    else:
        color = (0, 0, 255)  # Красный - низкий FPS
    
    # Текст
    text = f"FPS: {fps:.1f}"
    
    # Параметры шрифта
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    
    # Размер текста
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    
    # Позиция (верхний левый угол)
    margin = 10
    position = (margin, margin + text_height)
    
    # Фон для текста
    bg_color = (0, 0, 0)
    bg_margin = 5
    cv2.rectangle(
        frame,
        (position[0] - bg_margin, position[1] - text_height - bg_margin),
        (position[0] + text_width + bg_margin, position[1] + bg_margin),
        bg_color,
        -1
    )
    
    # Текст
    cv2.putText(frame, text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return frame

def draw_status_overlay(frame: np.ndarray, status: StreamStatus) -> np.ndarray:
    """
    Отрисовка статуса стрима
    
    Args:
        frame: Исходный кадр
        status: Статус стрима
        
    Returns:
        Кадр с отрисованным статусом
    """
    # Позиция (верхний левый угол, ниже FPS)
    margin = 10
    y_offset = 50
    
    # Статус включения
    status_text = "Стрим: ВКЛ" if status.stream_enabled else "Стрим: ВЫКЛ"
    status_color = (0, 255, 0) if status.stream_enabled else (0, 0, 255)
    
    # Разрешение
    res_text = f"Разрешение: {status.resolution[0]}x{status.resolution[1]}"
    res_color = (255, 255, 255)
    
    # Режим низкой задержки
    latency_text = "Режим: Низкая задержка" if status.low_latency else "Режим: Стандартный"
    latency_color = (255, 255, 0) if status.low_latency else (200, 200, 200)
    
    # Время
    time_text = f"Время: {time.strftime('%H:%M:%S')}"
    time_color = (200, 200, 200)
    
    texts = [
        (status_text, status_color),
        (res_text, res_color),
        (latency_text, latency_color),
        (time_text, time_color)
    ]
    
    # Параметры шрифта
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 1
    
    for i, (text, color) in enumerate(texts):
        position = (margin, y_offset + i * 25)
        
        # Фон
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        bg_margin = 3
        cv2.rectangle(
            frame,
            (position[0] - bg_margin, position[1] - text_height - bg_margin),
            (position[0] + text_width + bg_margin, position[1] + bg_margin),
            (0, 0, 0),
            -1
        )
        
        # Текст
        cv2.putText(frame, text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return frame

def draw_frame_info(frame: np.ndarray, frame_info: FrameInfo) -> np.ndarray:
    """
    Отрисовка информации о кадре
    
    Args:
        frame: Исходный кадр
        frame_info: Информация о кадре
        
    Returns:
        Кадр с отрисованной информацией
    """
    # Позиция (нижний левый угол)
    margin = 10
    y_offset = frame.shape[0] - 10
    
    # Информация о кадре
    size_text = f"Размер: {frame_info.width}x{frame_info.height}"
    channels_text = f"Каналы: {frame_info.channels}"
    time_text = f"Время: {frame_info.timestamp:.3f}"
    proc_text = f"Обработка: {frame_info.processing_time*1000:.1f} мс"
    
    texts = [
        (size_text, (255, 255, 255)),
        (channels_text, (200, 200, 200)),
        (time_text, (200, 200, 200)),
        (proc_text, (255, 255, 0))
    ]
    
    # Параметры шрифта
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    
    for i, (text, color) in enumerate(reversed(texts)):  # Рисуем снизу вверх
        position = (margin, y_offset - i * 20)
        
        # Фон
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        bg_margin = 2
        cv2.rectangle(
            frame,
            (position[0] - bg_margin, position[1] - text_height - bg_margin),
            (position[0] + text_width + bg_margin, position[1] + bg_margin),
            (0, 0, 0),
            -1
        )
        
        # Текст
        cv2.putText(frame, text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return frame

def draw_metrics_overlay(frame: np.ndarray, metrics: StreamMetrics) -> np.ndarray:
    """
    Отрисовка метрик производительности
    
    Args:
        frame: Исходный кадр
        metrics: Метрики производительности
        
    Returns:
        Кадр с отрисованными метриками
    """
    # Позиция (правый верхний угол)
    margin = 10
    x_offset = frame.shape[1] - margin
    
    # Метрики
    total_text = f"Всего кадров: {metrics.total_frames}"
    avg_fps_text = f"Средний FPS: {metrics.avg_fps:.1f}"
    min_fps_text = f"Мин FPS: {metrics.min_fps:.1f}"
    max_fps_text = f"Макс FPS: {metrics.max_fps:.1f}"
    
    texts = [
        (total_text, (255, 255, 255)),
        (avg_fps_text, (0, 255, 0)),
        (min_fps_text, (0, 255, 255)),
        (max_fps_text, (0, 0, 255))
    ]
    
    # Параметры шрифта
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 1
    
    for i, (text, color) in enumerate(texts):
        # Размер текста
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        # Позиция (справа налево)
        position = (x_offset - text_width - margin, margin + (i + 1) * 25)
        
        # Фон
        bg_margin = 3
        cv2.rectangle(
            frame,
            (position[0] - bg_margin, position[1] - text_height - bg_margin),
            (position[0] + text_width + bg_margin, position[1] + bg_margin),
            (0, 0, 0),
            -1
        )
        
        # Текст
        cv2.putText(frame, text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return frame

def draw_border_overlay(frame: np.ndarray, color: Tuple[int, int, int], thickness: int = 2) -> np.ndarray:
    """
    Отрисовка рамки вокруг кадра
    
    Args:
        frame: Исходный кадр
        color: Цвет рамки (B, G, R)
        thickness: Толщина рамки
        
    Returns:
        Кадр с рамкой
    """
    # Рамка по краям
    cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), color, thickness)
    
    # Угловые маркеры
    corner_size = 20
    corner_color = (255, 255, 255)
    
    # Верхний левый угол
    cv2.line(frame, (0, 0), (corner_size, 0), corner_color, thickness)
    cv2.line(frame, (0, 0), (0, corner_size), corner_color, thickness)
    
    # Верхний правый угол
    cv2.line(frame, (frame.shape[1]-1, 0), (frame.shape[1]-1-corner_size, 0), corner_color, thickness)
    cv2.line(frame, (frame.shape[1]-1, 0), (frame.shape[1]-1, corner_size), corner_color, thickness)
    
    # Нижний левый угол
    cv2.line(frame, (0, frame.shape[0]-1), (corner_size, frame.shape[0]-1), corner_color, thickness)
    cv2.line(frame, (0, frame.shape[0]-1), (0, frame.shape[0]-1-corner_size), corner_color, thickness)
    
    # Нижний правый угол
    cv2.line(frame, (frame.shape[1]-1, frame.shape[0]-1), (frame.shape[1]-1-corner_size, frame.shape[0]-1), corner_color, thickness)
    cv2.line(frame, (frame.shape[1]-1, frame.shape[0]-1), (frame.shape[1]-1, frame.shape[0]-1-corner_size), corner_color, thickness)
    
    return frame

def add_text_overlay(
    frame: np.ndarray, 
    text: str, 
    position: Tuple[int, int], 
    color: Tuple[int, int, int] = (255, 255, 255),
    font_scale: float = 1.0,
    thickness: int = 2,
    background: bool = True
) -> np.ndarray:
    """
    Добавление текстовой метки на кадр
    
    Args:
        frame: Исходный кадр
        text: Текст метки
        position: Позиция (x, y)
        color: Цвет текста
        font_scale: Масштаб шрифта
        thickness: Толщина линии
        background: Рисовать фон
        
    Returns:
        Кадр с текстовой меткой
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    if background:
        # Фон для текста
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        bg_margin = 5
        cv2.rectangle(
            frame,
            (position[0] - bg_margin, position[1] - text_height - bg_margin),
            (position[0] + text_width + bg_margin, position[1] + bg_margin),
            (0, 0, 0),
            -1
        )
    
    # Текст
    cv2.putText(frame, text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    
    return frame

def draw_center_crosshair(frame: np.ndarray, color: Tuple[int, int, int] = (0, 255, 0)) -> np.ndarray:
    """
    Отрисовка прицельной метки в центре кадра
    
    Args:
        frame: Исходный кадр
        color: Цвет метки
        
    Returns:
        Кадр с прицельной меткой
    """
    height, width = frame.shape[:2]
    center_x, center_y = width // 2, height // 2
    
    # Центральная точка
    cv2.circle(frame, (center_x, center_y), 5, color, -1)
    
    # Крест
    line_length = 20
    cv2.line(frame, (center_x - line_length, center_y), (center_x + line_length, center_y), color, 2)
    cv2.line(frame, (center_x, center_y - line_length), (center_x, center_y + line_length), color, 2)
    
    # Круг
    cv2.circle(frame, (center_x, center_y), 30, color, 1)
    
    return frame

def draw_resolution_indicator(frame: np.ndarray, resolution: Tuple[int, int]) -> np.ndarray:
    """
    Отрисовка индикатора разрешения
    
    Args:
        frame: Исходный кадр
        resolution: Текущее разрешение
        
    Returns:
        Кадр с индикатором разрешения
    """
    text = f"{resolution[0]}x{resolution[1]}"
    position = (frame.shape[1] - 150, frame.shape[0] - 20)
    
    return add_text_overlay(
        frame, text, position, 
        color=(255, 255, 255), 
        font_scale=0.8, 
        thickness=2,
        background=True
    )

def draw_debug_overlay(frame: np.ndarray, debug_info: dict) -> np.ndarray:
    """
    Отрисовка отладочной информации
    
    Args:
        frame: Исходный кадр
        debug_info: Словарь с отладочной информацией
        
    Returns:
        Кадр с отладочной информацией
    """
    if not debug_info:
        return frame
    
    # Позиция (правый нижний угол)
    margin = 10
    x_offset = frame.shape[1] - margin
    y_offset = frame.shape[0] - margin
    
    # Параметры шрифта
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    
    # Рисуем информацию
    for i, (key, value) in enumerate(debug_info.items()):
        text = f"{key}: {value}"
        
        # Размер текста
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        # Позиция
        position = (x_offset - text_width - margin, y_offset - i * 20)
        
        # Фон
        bg_margin = 2
        cv2.rectangle(
            frame,
            (position[0] - bg_margin, position[1] - text_height - bg_margin),
            (position[0] + text_width + bg_margin, position[1] + bg_margin),
            (0, 0, 0),
            -1
        )
        
        # Текст
        cv2.putText(frame, text, position, font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    
    return frame

def apply_visualization_overlay(
    frame: np.ndarray,
    status: Optional[StreamStatus] = None,
    frame_info: Optional[FrameInfo] = None,
    metrics: Optional[StreamMetrics] = None,
    show_fps: bool = True,
    show_status: bool = True,
    show_frame_info: bool = False,
    show_metrics: bool = False,
    show_center_crosshair: bool = False
) -> np.ndarray:
    """
    Применение всех визуальных наложений на кадр
    
    Args:
        frame: Исходный кадр
        status: Статус стрима
        frame_info: Информация о кадре
        metrics: Метрики производительности
        show_fps: Показывать FPS
        show_status: Показывать статус
        show_frame_info: Показывать информацию о кадре
        show_metrics: Показывать метрики
        show_center_crosshair: Показывать прицельную метку
        
    Returns:
        Кадр с наложениями
    """
    result = frame.copy()
    
    # FPS
    if show_fps and status:
        result = draw_fps_counter(result, status.fps)
    
    # Статус
    if show_status and status:
        result = draw_status_overlay(result, status)
    
    # Информация о кадре
    if show_frame_info and frame_info:
        result = draw_frame_info(result, frame_info)
    
    # Метрики
    if show_metrics and metrics:
        result = draw_metrics_overlay(result, metrics)
    
    # Прицельная метка
    if show_center_crosshair:
        result = draw_center_crosshair(result)
    
    return result