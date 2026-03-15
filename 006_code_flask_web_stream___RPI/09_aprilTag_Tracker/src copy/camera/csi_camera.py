"""
Реализация CSI камеры для Raspberry Pi
"""
import numpy as np
import time
from .base_camera import BaseCamera

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    print("⚠️ picamera2 not available, CSI camera will not work")


class CSICamera(BaseCamera):
    """Реализация для CSI камер (Raspberry Pi)"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.format = config.get('format', 'RGB888')
        self.buffers = config.get('buffers', 4)
        self.picam2 = None
        
        if not PICAMERA_AVAILABLE:
            raise ImportError("picamera2 is required for CSI camera")
    
    def initialize(self) -> bool:
        """Инициализация CSI камеры"""
        try:
            self.picam2 = Picamera2(0)
            
            # Настройка в зависимости от формата
            if self.format == "H264":
                config = self.picam2.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "H264"},
                    controls={"FrameRate": self.fps, "AfMode": 2},
                    buffer_count=self.buffers
                )
            else:
                config = self.picam2.create_video_configuration(
                    main={"size": (self.width, self.height), "format": self.format},
                    controls={"FrameRate": self.fps, "AfMode": 2},
                    buffer_count=self.buffers
                )
            
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(1)  # Даем камере прогреться
            
            # Проверка захвата
            test_frame = self.picam2.capture_array()
            if test_frame is None:
                print("❌ Failed to get frame from CSI camera")
                return False
            
            # Обновляем реальные параметры
            self.height, self.width = test_frame.shape[:2]
            
            # Измеряем реальный FPS
            start_time = time.time()
            for _ in range(30):
                self.picam2.capture_array()
            end_time = time.time()
            actual_fps = 30 / (end_time - start_time)
            
            print(f"✅ CSI camera: {self.width}x{self.height} @ {actual_fps:.1f}fps ({self.format})")
            
            return True
            
        except Exception as e:
            print(f"❌ CSI camera initialization error: {e}")
            return False
    
    def get_frame(self) -> np.ndarray:
        """Получение кадра"""
        if self.picam2 is None:
            return None
        
        return self.picam2.capture_array()
    
    def release(self):
        """Освобождение ресурсов"""
        if self.picam2:
            self.picam2.stop()
