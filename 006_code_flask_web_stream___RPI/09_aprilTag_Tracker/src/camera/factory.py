"""
Фабрика для создания камер
"""
from .usb_camera import USBCamera
from .csi_camera import CSICamera


class CameraFactory:
    """Фабрика для создания камер"""
    
    @staticmethod
    def create_camera(camera_type: str, config: dict):
        """
        Создание камеры по типу
        
        Args:
            camera_type: 'usb' или 'csi'
            config: конфигурация камеры
            
        Returns:
            Экземпляр камеры
        """
        if camera_type == 'usb':
            return USBCamera(config)
        elif camera_type == 'csi':
            return CSICamera(config)
        else:
            raise ValueError(f"Unknown camera type: {camera_type}")
