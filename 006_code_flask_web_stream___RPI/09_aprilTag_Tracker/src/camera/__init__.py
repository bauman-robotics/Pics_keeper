"""
Пакет для работы с камерами
"""
from .base_camera import BaseCamera
from .usb_camera import USBCamera
from .csi_camera import CSICamera
from .factory import CameraFactory

__all__ = ['BaseCamera', 'USBCamera', 'CSICamera', 'CameraFactory']