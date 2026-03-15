"""
Реализация USB камеры через OpenCV
"""
import cv2
import numpy as np
from .base_camera import BaseCamera


class USBCamera(BaseCamera):
    """Реализация для USB камер (OpenCV)"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.device = config.get('device', 0)
        self.fps_target = config.get('fps_target', 30)
        self.init_mode = config.get('init_mode', 'MJPEG')
        self.config_mode = config.get('config_mode', 'NEW')
        self.cap = None
    
    def initialize(self) -> bool:
        """Инициализация USB камеры"""
        try:
            if self.config_mode == "OLD":
                self.cap = cv2.VideoCapture(self.device)
            else:
                self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
                
                if self.init_mode == "MJPEG":
                    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
                    self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            
            # Установка параметров
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps_target)
            
            # Проверка захвата
            ret, test_frame = self.cap.read()
            if not ret or test_frame is None:
                print("❌ Failed to get frame from camera")
                return False
            
            # Обновляем реальные параметры
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            print(f"✅ USB camera: {self.width}x{self.height} @ {actual_fps:.1f}fps")
            
            return True
            
        except Exception as e:
            print(f"❌ Camera initialization error: {e}")
            return False
    
    def get_frame(self) -> np.ndarray:
        """Получение кадра"""
        if self.cap is None:
            return None
        
        ret, frame = self.cap.read()
        return frame if ret else None
    
    def release(self):
        """Освобождение ресурсов"""
        if self.cap:
            self.cap.release()
