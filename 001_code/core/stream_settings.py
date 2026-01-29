#!/usr/bin/env python3
"""
Модуль с классами данных для настроек стрима

Содержит dataclass-ы для хранения настроек стрима, статуса и метрик.
"""

from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class StreamSettings:
    """Настройки видеопотока"""
    enabled: bool = True
    target_width: int = 1280
    target_height: int = 720
    max_fps: float = 30.0
    low_latency: bool = True
    show_fps: bool = True
    show_status: bool = True
    show_frame_info: bool = False

@dataclass
class StreamStatus:
    """Статус видеопотока"""
    fps: float
    resolution: Tuple[int, int]
    stream_enabled: bool
    low_latency: bool
    timestamp: float

@dataclass
class FrameInfo:
    """Информация о кадре"""
    width: int
    height: int
    channels: int
    timestamp: float
    processing_time: float

@dataclass
class StreamMetrics:
    """Метрики производительности стрима"""
    total_frames: int
    dropped_frames: int
    avg_fps: float
    min_fps: float
    max_fps: float

@dataclass
class StreamConfig:
    """Конфигурация стрима"""
    width: int
    height: int
    fps: float
    quality: int = 50
    analysis_enabled: bool = False
    low_latency: bool = True

@dataclass
class CameraStreamSettings:
    """Настройки камеры для стрима"""
    camera_type: str = "imx708"
    sensor_mode: int = 0
    exposure_time: int = 40000
    analogue_gain: float = 2.0
    digital_gain: float = 1.0
    awb_enable: bool = True
    ae_enable: bool = True
    noise_reduction_mode: int = 1

@dataclass
class StreamWindowSettings:
    """Настройки окна стрима"""
    title: str = "Stream"
    fullscreen: bool = False
    resizable: bool = True
    show_controls: bool = True

@dataclass
class StreamVisualizationSettings:
    """Настройки визуализации стрима"""
    show_fps: bool = True
    show_status: bool = True
    show_frame_info: bool = False
    show_metrics: bool = False
    show_timestamp: bool = False
    fps_position: Tuple[int, int] = (10, 30)
    status_position: Tuple[int, int] = (10, 60)
    font_scale: float = 0.7
    font_thickness: int = 2

@dataclass
class StreamScalingSettings:
    """Настройки масштабирования стрима"""
    method: str = "auto"  # "auto", "nearest", "linear", "area", "cubic"
    preserve_aspect_ratio: bool = True
    padding_color: Tuple[int, int, int] = (0, 0, 0)
    interpolation: int = 3  # cv2.INTER_AREA

@dataclass
class StreamPerformanceSettings:
    """Настройки производительности стрима"""
    max_buffer_size: int = 3
    frame_timeout: float = 1.0
    enable_metrics: bool = True
    metrics_interval: float = 5.0
    enable_profiling: bool = False

@dataclass
class StreamDebugSettings:
    """Настройки отладки стрима"""
    enabled: bool = False
    show_processing_time: bool = False
    show_frame_stats: bool = False
    log_level: str = "INFO"  # "DEBUG", "INFO", "WARNING", "ERROR"
    save_debug_frames: bool = False
    debug_dir: str = "./debug_frames"

# Константы по умолчанию
DEFAULT_STREAM_SETTINGS = StreamSettings()
DEFAULT_STREAM_CONFIG = StreamConfig(width=1280, height=720, fps=30.0)
DEFAULT_CAMERA_SETTINGS = CameraStreamSettings()
DEFAULT_WINDOW_SETTINGS = StreamWindowSettings()
DEFAULT_VISUALIZATION_SETTINGS = StreamVisualizationSettings()
DEFAULT_SCALING_SETTINGS = StreamScalingSettings()
DEFAULT_PERFORMANCE_SETTINGS = StreamPerformanceSettings()
DEFAULT_DEBUG_SETTINGS = StreamDebugSettings()

# Поддерживаемые разрешения
SUPPORTED_RESOLUTIONS = [
    (640, 480),
    (800, 600),
    (1024, 768),
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160)
]

# Поддерживаемые FPS
SUPPORTED_FPS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 120]

# Поддерживаемые методы масштабирования
SCALING_METHODS = {
    "nearest": 0,    # cv2.INTER_NEAREST
    "linear": 1,     # cv2.INTER_LINEAR
    "area": 3,       # cv2.INTER_AREA
    "cubic": 2,      # cv2.INTER_CUBIC
    "lanczos": 4     # cv2.INTER_LANCZOS4
}

def create_default_stream_settings() -> StreamSettings:
    """Создание настроек стрима по умолчанию"""
    return StreamSettings(
        enabled=True,
        target_width=1280,
        target_height=720,
        max_fps=30.0,
        low_latency=True,
        show_fps=True,
        show_status=True,
        show_frame_info=False
    )

def create_stream_settings_from_dict(settings_dict: dict) -> StreamSettings:
    """Создание настроек стрима из словаря"""
    return StreamSettings(**settings_dict)

def validate_stream_settings(settings: StreamSettings) -> bool:
    """Валидация настроек стрима"""
    if settings.target_width <= 0 or settings.target_height <= 0:
        return False
    if settings.max_fps <= 0:
        return False
    if settings.max_fps > 120:
        return False
    return True

def get_optimal_stream_settings(
    max_width: int = 1920,
    max_height: int = 1080,
    max_fps: float = 30.0
) -> StreamSettings:
    """Получение оптимальных настроек стрима"""
    # Выбираем разрешение не больше максимального
    width = min(1280, max_width)
    height = min(720, max_height)
    
    # Выбираем FPS не больше максимального
    fps = min(30.0, max_fps)
    
    return StreamSettings(
        enabled=True,
        target_width=width,
        target_height=height,
        max_fps=fps,
        low_latency=True,
        show_fps=True,
        show_status=True,
        show_frame_info=False
    )

def get_low_latency_settings() -> StreamSettings:
    """Настройки для низкой задержки"""
    return StreamSettings(
        enabled=True,
        target_width=640,
        target_height=480,
        max_fps=60.0,
        low_latency=True,
        show_fps=False,
        show_status=False,
        show_frame_info=False
    )

def get_high_quality_settings() -> StreamSettings:
    """Настройки для высокого качества"""
    return StreamSettings(
        enabled=True,
        target_width=1920,
        target_height=1080,
        max_fps=30.0,
        low_latency=False,
        show_fps=True,
        show_status=True,
        show_frame_info=True
    )