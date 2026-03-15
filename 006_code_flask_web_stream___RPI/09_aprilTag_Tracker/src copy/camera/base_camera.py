"""
Абстрактный базовый класс для камер
"""
from abc import ABC, abstractmethod
import numpy as np
import cv2
from pathlib import Path


class BaseCamera(ABC):
    """Абстрактный базовый класс для всех камер"""
    
    def __init__(self, config: dict):
        self.config = config
        self.width = config.get('width', 640)
        self.height = config.get('height', 480)
        self.fps = config.get('fps', 30)
        self.camera_matrix = None
        self.dist_coeffs = None
        self._is_running = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """Инициализация камеры"""
        pass
    
    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """Получение кадра"""
        pass
    
    @abstractmethod
    def release(self):
        """Освобождение ресурсов"""
        pass
    
    def load_calibration(self, calib_config: dict):
        """Загрузка калибровочных данных"""
        matrix_file = Path(calib_config['matrix_file'])
        dist_file = Path(calib_config['dist_file'])
        calib_width = calib_config['calib_width']
        calib_height = calib_config['calib_height']
        
        if not matrix_file.exists() or not dist_file.exists():
            print(f"⚠️ Calibration files not found, using default matrices")
            self.camera_matrix = np.eye(3)
            self.dist_coeffs = np.zeros((4, 1))
            return
        
        self.camera_matrix = np.load(str(matrix_file))
        self.dist_coeffs = np.load(str(dist_file))
        
        # Масштабирование под текущее разрешение
        if self.width != calib_width:
            scale_x = self.width / calib_width
            scale_y = self.height / calib_height
            
            self.camera_matrix[0,0] *= scale_x
            self.camera_matrix[1,1] *= scale_y
            self.camera_matrix[0,2] *= scale_x
            self.camera_matrix[1,2] *= scale_y
            
            print(f"✅ Camera matrix scaled: {scale_x:.2f}x, {scale_y:.2f}y")
    
    def get_camera_params(self):
        """Получение параметров камеры для AprilTag"""
        return [
            self.camera_matrix[0,0],
            self.camera_matrix[1,1],
            self.camera_matrix[0,2],
            self.camera_matrix[1,2]
        ]
