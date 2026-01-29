#!/usr/bin/env python3
"""
Модуль core для стрима

Содержит основные классы и функции для управления видеопотоком с масштабированием.
"""

# Импортируем основные классы
from .stream_manager import StreamManager, StreamFrame
from .webcam_stream import WebcamStream, WebcamStreamConfig
from .stream_manager_universal import UniversalStreamManager, UniversalStreamConfig
from .stream_settings import (
    StreamSettings, StreamStatus, FrameInfo, StreamMetrics,
    StreamConfig, CameraStreamSettings, StreamWindowSettings,
    StreamVisualizationSettings, StreamScalingSettings,
    StreamPerformanceSettings, StreamDebugSettings,
    create_default_stream_settings, create_stream_settings_from_dict,
    validate_stream_settings, get_optimal_stream_settings,
    get_low_latency_settings, get_high_quality_settings
)
from .stream_visualization import (
    draw_fps_counter, draw_status_overlay, draw_frame_info,
    draw_metrics_overlay, draw_border_overlay, add_text_overlay,
    draw_center_crosshair, draw_resolution_indicator,
    draw_debug_overlay, apply_visualization_overlay
)
from .stream_scaling import (
    scale_frame_to_target_resolution, get_scale_factor,
    calculate_target_resolution, resize_with_aspect_ratio,
    pad_to_target_resolution, smart_resize, get_interpolation_method,
    optimize_resolution_for_streaming, get_common_stream_resolutions,
    validate_resolution, get_aspect_ratio, is_widescreen,
    get_resolution_info
)

# Версия модуля
__version__ = "1.0.0"

# Экспортируемые символы
__all__ = [
    # StreamManager
    'StreamManager', 'StreamFrame',
    
    # StreamSettings
    'StreamSettings', 'StreamStatus', 'FrameInfo', 'StreamMetrics',
    'StreamConfig', 'CameraStreamSettings', 'StreamWindowSettings',
    'StreamVisualizationSettings', 'StreamScalingSettings',
    'StreamPerformanceSettings', 'StreamDebugSettings',
    'create_default_stream_settings', 'create_stream_settings_from_dict',
    'validate_stream_settings', 'get_optimal_stream_settings',
    'get_low_latency_settings', 'get_high_quality_settings',
    
    # StreamVisualization
    'draw_fps_counter', 'draw_status_overlay', 'draw_frame_info',
    'draw_metrics_overlay', 'draw_border_overlay', 'add_text_overlay',
    'draw_center_crosshair', 'draw_resolution_indicator',
    'draw_debug_overlay', 'apply_visualization_overlay',
    
    # StreamScaling
    'scale_frame_to_target_resolution', 'get_scale_factor',
    'calculate_target_resolution', 'resize_with_aspect_ratio',
    'pad_to_target_resolution', 'smart_resize', 'get_interpolation_method',
    'optimize_resolution_for_streaming', 'get_common_stream_resolutions',
    'validate_resolution', 'get_aspect_ratio', 'is_widescreen',
    'get_resolution_info'
]