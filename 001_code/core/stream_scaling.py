#!/usr/bin/env python3
"""
Модуль масштабирования изображения для стрима

Содержит функции для масштабирования изображений до заданного разрешения
с различными методами и опциями.
"""

import cv2
import numpy as np
from typing import Tuple, Optional
from .stream_settings import StreamScalingSettings

def scale_frame_to_target_resolution(
    frame: np.ndarray, 
    target_width: int, 
    target_height: int,
    method: str = "auto"
) -> np.ndarray:
    """
    Масштабирование кадра до целевого разрешения
    
    Args:
        frame: Исходный кадр
        target_width: Целевая ширина
        target_height: Целевая высота
        method: Метод масштабирования
        
    Returns:
        Масштабированный кадр
    """
    if frame is None or frame.size == 0:
        return frame
    
    # Текущие размеры
    current_height, current_width = frame.shape[:2]
    
    # Если уже нужного размера
    if current_width == target_width and current_height == target_height:
        return frame
    
    # Выбираем метод интерполяции
    interpolation = get_interpolation_method(
        current_width, current_height, 
        target_width, target_height, 
        method
    )
    
    # Масштабирование
    scaled_frame = cv2.resize(
        frame, 
        (target_width, target_height), 
        interpolation=interpolation
    )
    
    return scaled_frame

def get_scale_factor(
    original_width: int, 
    original_height: int, 
    target_width: int, 
    target_height: int
) -> float:
    """
    Получение коэффициента масштабирования
    
    Args:
        original_width: Исходная ширина
        original_height: Исходная высота
        target_width: Целевая ширина
        target_height: Целевая высота
        
    Returns:
        Коэффициент масштабирования
    """
    scale_x = target_width / original_width
    scale_y = target_height / original_height
    
    # Возвращаем минимальный коэффициент для сохранения пропорций
    return min(scale_x, scale_y)

def calculate_target_resolution(
    source_width: int, 
    source_height: int, 
    max_width: int, 
    max_height: int,
    preserve_aspect_ratio: bool = True
) -> Tuple[int, int]:
    """
    Расчет целевого разрешения с учетом ограничений
    
    Args:
        source_width: Исходная ширина
        source_height: Исходная высота
        max_width: Максимальная ширина
        max_height: Максимальная высота
        preserve_aspect_ratio: Сохранять пропорции
        
    Returns:
        Целевое разрешение (ширина, высота)
    """
    if not preserve_aspect_ratio:
        return (
            min(source_width, max_width),
            min(source_height, max_height)
        )
    
    # Сохраняем пропорции
    scale_x = max_width / source_width
    scale_y = max_height / source_height
    scale = min(scale_x, scale_y)
    
    target_width = int(source_width * scale)
    target_height = int(source_height * scale)
    
    # Округляем до четных чисел (требование некоторых кодеков)
    target_width = target_width if target_width % 2 == 0 else target_width - 1
    target_height = target_height if target_height % 2 == 0 else target_height - 1
    
    return (target_width, target_height)

def resize_with_aspect_ratio(
    frame: np.ndarray, 
    target_width: int, 
    target_height: int,
    method: str = "auto"
) -> np.ndarray:
    """
    Масштабирование с сохранением пропорций
    
    Args:
        frame: Исходный кадр
        target_width: Целевая ширина
        target_height: Целевая высота
        method: Метод масштабирования
        
    Returns:
        Масштабированный кадр
    """
    if frame is None or frame.size == 0:
        return frame
    
    current_height, current_width = frame.shape[:2]
    
    # Рассчитываем коэффициенты масштабирования
    scale_x = target_width / current_width
    scale_y = target_height / current_height
    scale = min(scale_x, scale_y)
    
    # Новые размеры
    new_width = int(current_width * scale)
    new_height = int(current_height * scale)
    
    # Масштабируем
    scaled_frame = cv2.resize(
        frame, 
        (new_width, new_height), 
        interpolation=get_interpolation_method(current_width, current_height, new_width, new_height, method)
    )
    
    return scaled_frame

def pad_to_target_resolution(
    frame: np.ndarray, 
    target_width: int, 
    target_height: int,
    padding_color: Tuple[int, int, int] = (0, 0, 0)
) -> np.ndarray:
    """
    Добавление паддинга до целевого разрешения
    
    Args:
        frame: Масштабированный кадр
        target_width: Целевая ширина
        target_height: Целевая высота
        padding_color: Цвет паддинга
        
    Returns:
        Кадр с паддингом
    """
    if frame is None or frame.size == 0:
        return frame
    
    current_height, current_width = frame.shape[:2]
    
    # Если уже нужного размера
    if current_width == target_width and current_height == target_height:
        return frame
    
    # Вычисляем паддинг
    pad_left = (target_width - current_width) // 2
    pad_right = target_width - current_width - pad_left
    pad_top = (target_height - current_height) // 2
    pad_bottom = target_height - current_height - pad_top
    
    # Добавляем паддинг
    if len(frame.shape) == 3:
        # Цветное изображение
        padded_frame = cv2.copyMakeBorder(
            frame,
            pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT,
            value=padding_color
        )
    else:
        # Монохромное изображение
        padded_frame = cv2.copyMakeBorder(
            frame,
            pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT,
            value=padding_color[0]  # Используем только первый канал
        )
    
    return padded_frame

def smart_resize(
    frame: np.ndarray, 
    target_width: int, 
    target_height: int,
    scaling_settings: Optional[StreamScalingSettings] = None
) -> np.ndarray:
    """
    Умное масштабирование с учетом настроек
    
    Args:
        frame: Исходный кадр
        target_width: Целевая ширина
        target_height: Целевая высота
        scaling_settings: Настройки масштабирования
        
    Returns:
        Масштабированный кадр
    """
    if frame is None or frame.size == 0:
        return frame
    
    if scaling_settings is None:
        scaling_settings = StreamScalingSettings()
    
    # Сохранение пропорций
    if scaling_settings.preserve_aspect_ratio:
        # Сначала масштабируем с сохранением пропорций
        scaled_frame = resize_with_aspect_ratio(
            frame, target_width, target_height, scaling_settings.method
        )
        
        # Затем добавляем паддинг до целевого разрешения
        scaled_frame = pad_to_target_resolution(
            scaled_frame, target_width, target_height, scaling_settings.padding_color
        )
    else:
        # Простое масштабирование
        scaled_frame = scale_frame_to_target_resolution(
            frame, target_width, target_height, scaling_settings.method
        )
    
    return scaled_frame

def get_interpolation_method(
    src_width: int, 
    src_height: int, 
    dst_width: int, 
    dst_height: int, 
    method: str = "auto"
) -> int:
    """
    Получение метода интерполяции в зависимости от направления масштабирования
    
    Args:
        src_width: Исходная ширина
        src_height: Исходная высота
        dst_width: Целевая ширина
        dst_height: Целевая высота
        method: Желаемый метод
        
    Returns:
        Константа OpenCV для интерполяции
    """
    # Определяем направление масштабирования
    scale_x = dst_width / src_width
    scale_y = dst_height / src_height
    
    # Если масштабирование вниз (уменьшение)
    if scale_x < 1.0 or scale_y < 1.0:
        if method == "auto":
            return cv2.INTER_AREA  # Лучше для уменьшения
        elif method == "linear":
            return cv2.INTER_LINEAR
        elif method == "cubic":
            return cv2.INTER_CUBIC
        else:
            return cv2.INTER_AREA
    
    # Если масштабирование вверх (увеличение)
    else:
        if method == "auto":
            return cv2.INTER_LINEAR  # Хороший баланс качества и скорости
        elif method == "nearest":
            return cv2.INTER_NEAREST
        elif method == "cubic":
            return cv2.INTER_CUBIC
        elif method == "lanczos":
            return cv2.INTER_LANCZOS4
        else:
            return cv2.INTER_LINEAR

def optimize_resolution_for_streaming(
    source_width: int, 
    source_height: int,
    max_bandwidth: int = 2000000,  # 2 Мбит/с
    target_fps: int = 30
) -> Tuple[int, int]:
    """
    Оптимизация разрешения для стриминга
    
    Args:
        source_width: Исходная ширина
        source_height: Исходная высота
        max_bandwidth: Максимальная пропускная способность (бит/с)
        target_fps: Целевой FPS
        
    Returns:
        Оптимальное разрешение
    """
    # Оценка требуемой пропускной способности
    # Приблизительная формула: ширина * высота * FPS * 3 (RGB) / сжатие
    compression_ratio = 20  # Примерное сжатие для JPEG
    
    def calculate_bandwidth(width: int, height: int) -> int:
        return (width * height * target_fps * 3) // compression_ratio
    
    # Начинаем с исходного разрешения и уменьшаем
    current_width, current_height = source_width, source_height
    
    while calculate_bandwidth(current_width, current_height) > max_bandwidth:
        # Уменьшаем в 1.2 раза
        current_width = int(current_width / 1.2)
        current_height = int(current_height / 1.2)
        
        # Ограничиваем минимальное разрешение
        if current_width < 320 or current_height < 240:
            current_width = 320
            current_height = 240
            break
    
    # Округляем до четных чисел
    current_width = current_width if current_width % 2 == 0 else current_width - 1
    current_height = current_height if current_height % 2 == 0 else current_height - 1
    
    return (current_width, current_height)

def get_common_stream_resolutions() -> list:
    """Получение списка популярных разрешений для стриминга"""
    return [
        (320, 240),    # QVGA
        (640, 480),    # VGA
        (800, 600),    # SVGA
        (1024, 768),   # XGA
        (1280, 720),   # HD
        (1920, 1080),  # Full HD
        (2560, 1440),  # 2K
        (3840, 2160),  # 4K
    ]

def validate_resolution(width: int, height: int) -> bool:
    """Проверка валидности разрешения"""
    if width <= 0 or height <= 0:
        return False
    if width > 8192 or height > 8192:  # Ограничение OpenCV
        return False
    if width % 2 != 0 or height % 2 != 0:  # Требование четности
        return False
    return True

def get_aspect_ratio(width: int, height: int) -> float:
    """Получение соотношения сторон"""
    if height == 0:
        return 0
    return width / height

def is_widescreen(width: int, height: int) -> bool:
    """Проверка, является ли разрешение широкоформатным"""
    aspect_ratio = get_aspect_ratio(width, height)
    return aspect_ratio >= 1.7  # 16:9 = 1.777...

def get_resolution_info(width: int, height: int) -> dict:
    """Получение информации о разрешении"""
    aspect_ratio = get_aspect_ratio(width, height)
    
    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(aspect_ratio, 3),
        "total_pixels": width * height,
        "is_widescreen": is_widescreen(width, height),
        "is_hd": width >= 1280 and height >= 720,
        "is_full_hd": width >= 1920 and height >= 1080,
        "is_4k": width >= 3840 and height >= 2160
    }