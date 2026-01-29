#!/usr/bin/env python3
"""
Классы настроек для Pics_keeper
"""

from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class CameraSettings:
    """Настройки камеры"""
    camera_type: str = 'imx708'
    resolution: str = 'full'  # 'full' или 'stream'
    exposure_time: int = 40000
    analogue_gain: float = 2.0
    digital_gain: float = 1.0
    ae_enable: bool = False
    awb_enable: bool = True
    noise_reduction_mode: int = 2
    af_enable: bool = False
    lens_position: float = 0.5
    af_mode: int = 0
    af_range: int = 0
    
    @property
    def full_resolution(self) -> Tuple[int, int]:
        """Полное разрешение камеры"""
        from .camera_profiles import get_camera_profile
        profile = get_camera_profile(self.camera_type)
        return profile['full_resolution']
    
    @property
    def sensor_size(self) -> Tuple[float, float]:
        """Размер сенсора"""
        from .camera_profiles import get_camera_profile
        profile = get_camera_profile(self.camera_type)
        return profile['sensor_size']

@dataclass
class StreamSettings:
    """Настройки стрима"""
    enabled: bool = True
    width: int = 1280
    height: int = 720
    fps: int = 30
    quality: int = 50
    analysis: bool = False
    low_latency: bool = True
    port: int = 8080
    ae_enable: bool = True
    exposure_time: int = 40000
    analogue_gain: float = 2.0
    noise_reduction: int = 1

@dataclass
class CaptureSettings:
    """Настройки съемки"""
    delay: float = 0
    count: int = 20
    output_dir: str = 'calibration_images'
    jpeg_quality: int = 95
    max_angle: float = 45
    warn_angle: float = 30
    force_capture: bool = False

@dataclass
class PreviewSettings:
    """Настройки предпросмотра"""
    enabled: bool = False

@dataclass
class DebugSettings:
    """Настройки отладки"""
    enabled: bool = False

@dataclass
class ApplicationSettings:
    """Все настройки приложения"""
    camera: CameraSettings
    stream: StreamSettings
    capture: CaptureSettings
    preview: PreviewSettings
    debug: DebugSettings
    
    @classmethod
    def from_args(cls, args):
        """Создание настроек из аргументов командной строки"""
        from .camera_profiles import get_default_settings
        
        defaults = get_default_settings()
        
        # Настройки камеры
        camera = CameraSettings(
            camera_type=getattr(args, 'camera', defaults['camera_type']),
            resolution=getattr(args, 'resolution', defaults.get('resolution', 'full')),
            exposure_time=getattr(args, 'exposure_time', defaults['exposure_time']),
            analogue_gain=getattr(args, 'analogue_gain', defaults['analogue_gain']),
            ae_enable=getattr(args, 'ae_enable', defaults['ae_enable']),
            af_enable=getattr(args, 'af_enable', defaults['af_enable']),
            lens_position=getattr(args, 'lens_position', defaults['lens_position'])
        )
        
        # Настройки стрима
        stream = StreamSettings(
            enabled=getattr(args, 'stream', defaults.get('stream_enabled', True)),
            width=getattr(args, 'stream_width', defaults.get('stream_width', 1280)),
            height=getattr(args, 'stream_height', defaults.get('stream_height', 720)),
            fps=getattr(args, 'stream_fps', defaults.get('stream_fps', 30)),
            quality=getattr(args, 'stream_quality', defaults.get('stream_quality', 50)),
            analysis=getattr(args, 'stream_analysis', defaults.get('stream_analysis', False)),
            low_latency=getattr(args, 'low_latency', defaults.get('stream_low_latency', True)),
            port=getattr(args, 'stream_port', defaults.get('stream_port', 8080))
        )
        
        # Настройки съемки
        capture = CaptureSettings(
            delay=getattr(args, 'delay', defaults['delay']),
            count=getattr(args, 'count', defaults['count']),
            output_dir=getattr(args, 'output_dir', defaults['output_dir']),
            jpeg_quality=getattr(args, 'jpeg_quality', defaults['jpeg_quality']),
            max_angle=getattr(args, 'max_angle', defaults['max_angle']),
            warn_angle=getattr(args, 'warn_angle', defaults['warn_angle']),
            force_capture=getattr(args, 'force_capture', defaults['force_capture'])
        )
        
        # Настройки предпросмотра
        preview = PreviewSettings(
            enabled=getattr(args, 'preview', defaults['preview_enabled'])
        )
        
        # Настройки отладки
        debug = DebugSettings(
            enabled=getattr(args, 'debug', defaults['debug'])
        )
        
        return cls(
            camera=camera,
            stream=stream,
            capture=capture,
            preview=preview,
            debug=debug
        )
    
    def to_dict(self) -> dict:
        """Преобразование в словарь"""
        return {
            'camera': {
                'camera_type': self.camera.camera_type,
                'resolution': self.camera.resolution,
                'exposure_time': self.camera.exposure_time,
                'analogue_gain': self.camera.analogue_gain,
                'ae_enable': self.camera.ae_enable,
                'af_enable': self.camera.af_enable,
                'lens_position': self.camera.lens_position
            },
            'stream': {
                'enabled': self.stream.enabled,
                'width': self.stream.width,
                'height': self.stream.height,
                'fps': self.stream.fps,
                'quality': self.stream.quality,
                'analysis': self.stream.analysis,
                'low_latency': self.stream.low_latency,
                'port': self.stream.port
            },
            'capture': {
                'delay': self.capture.delay,
                'count': self.capture.count,
                'output_dir': self.capture.output_dir,
                'jpeg_quality': self.capture.jpeg_quality,
                'max_angle': self.capture.max_angle,
                'warn_angle': self.capture.warn_angle,
                'force_capture': self.capture.force_capture
            },
            'preview': {
                'enabled': self.preview.enabled
            },
            'debug': {
                'enabled': self.debug.enabled
            }
        }