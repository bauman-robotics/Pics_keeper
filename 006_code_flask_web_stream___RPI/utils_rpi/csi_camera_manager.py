#!/usr/bin/env python3
"""
CSI Camera Manager для работы с камерами Raspberry Pi через Picamera2
"""

import sys
import os

# Добавляем путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("⚠️  Picamera2 не установлен. CSI камеры не будут доступны.")
    print("   Установите: pip install picamera2")

class CSICameraManager:
    """Менеджер для работы с CSI камерами через Picamera2"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.cameras = []
        self.current_camera = None
        self.current_picam2 = None
        
        if PICAMERA2_AVAILABLE:
            self.detect_csi_cameras()
        else:
            logger.log_warning("Picamera2 не доступен. CSI камеры не будут работать.")
    
    def detect_csi_cameras(self):
        """Обнаружение CSI камер через Picamera2"""
        if not PICAMERA2_AVAILABLE:
            self.logger.log_info("Picamera2 не доступен, пропускаем обнаружение CSI камер")
            return []
        
        try:
            self.logger.log_info("🔍 Поиск CSI камер через Picamera2...")
            print("🔍 Поиск CSI камер через Picamera2...")
            
            # Пробуем обнаружить камеры через Picamera2
            for cam_idx in range(2):  # Проверяем до 2 камер
                try:
                    print(f"  Проверка камеры #{cam_idx}...", end=' ', flush=True)
                    
                    picam2 = Picamera2(cam_idx)
                    camera_properties = picam2.camera_properties
                    
                    if camera_properties:
                        model = camera_properties.get('Model', 'Unknown CSI Camera')
                        print(f"✓ найдена: {model}")
                        
                        # Получаем информацию о камере
                        cam_info = {
                            'index': cam_idx,
                            'device': f'csi_{cam_idx}',
                            'name': f'CSI Camera {cam_idx} ({model})',
                            'type': 'CSI',
                            'model': model,
                            'picamera2': True
                        }
                        
                        self.cameras.append(cam_info)
                        self.logger.log_info(f"Обнаружена CSI камера: {model} (индекс: {cam_idx})")
                        
                        picam2.close()
                    else:
                        print("✗ нет камеры")
                        picam2.close()
                        if cam_idx == 0:
                            break  # На первой камере должна быть ошибка если нет камер
                        
                except Exception as e:
                    print(f"✗ ошибка: {str(e)[:30]}")
                    if cam_idx == 0:
                        # На первой камере должна быть ошибка если нет камер
                        print("  Вероятно, CSI камера не подключена или не включена")
                        self.logger.log_warning("CSI камера не обнаружена. Проверьте подключение.")
                        break
        
        except Exception as e:
            print(f"  Ошибка обнаружения CSI: {e}")
            self.logger.log_error(f"Ошибка обнаружения CSI камер: {e}")
        
        if not self.cameras:
            self.logger.log_info("CSI камеры не обнаружены")
        else:
            self.logger.log_info(f"Обнаружено CSI камер: {len(self.cameras)}")
        
        return self.cameras
    
    def open_csi_camera(self, camera_idx):
        """Открытие CSI камеры через Picamera2"""
        if not PICAMERA2_AVAILABLE:
            self.logger.log_error("Попытка открыть CSI камеру без Picamera2")
            return None
        
        try:
            print(f"📹 Открытие CSI камеры #{camera_idx}...")
            self.logger.log_info(f"Открытие CSI камеры #{camera_idx}")
            
            picam2 = Picamera2(camera_idx)
            
            # Используем настройки из конфига
            width = self.config.get('camera', {}).get('width', 1280)
            height = self.config.get('camera', {}).get('height', 720)
            fps = self.config.get('camera', {}).get('fps', 30)
            
            # Создаем конфигурацию для видео
            config = picam2.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"},
                controls={"FrameRate": fps, "AwbEnable": True}
            )
            
            picam2.configure(config)
            picam2.start()
            
            # Даем камере время на инициализацию
            import time
            time.sleep(1)
            
            print(f"✅ CSI камера #{camera_idx} открыта успешно")
            print(f"   Разрешение: {width}x{height}, FPS: {fps}")
            
            self.logger.log_info(f"CSI камера #{camera_idx} открыта ({width}x{height} @ {fps}fps)")
            
            self.current_camera = camera_idx
            self.current_picam2 = picam2
            
            return picam2
            
        except Exception as e:
            print(f"❌ Ошибка открытия CSI камеры #{camera_idx}: {e}")
            self.logger.log_error(f"Ошибка открытия CSI камеры #{camera_idx}: {e}")
            return None
    
    def capture_frame(self):
        """Захват кадра с CSI камеры"""
        if not self.current_picam2:
            return None
        
        try:
            # Захватываем кадр
            array = self.current_picam2.capture_array()
            
            # Picamera2 возвращает RGB, конвертируем в BGR для OpenCV
            if len(array.shape) == 3 and array.shape[2] == 3:
                import cv2
                frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                return frame
            
            return array
            
        except Exception as e:
            self.logger.log_error(f"Ошибка захвата кадра с CSI камеры: {e}")
            return None
    
    def close_current(self):
        """Закрытие текущей CSI камеры"""
        if self.current_picam2:
            try:
                self.current_picam2.stop()
                self.current_picam2.close()
                self.current_picam2 = None
                self.current_camera = None
                print("✅ CSI камера закрыта")
                self.logger.log_info("CSI камера закрыта")
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии CSI камеры: {e}")
                self.logger.log_error(f"Ошибка при закрытии CSI камеры: {e}")
    
    def get_camera_info(self, camera_idx):
        """Получить информацию о конкретной CSI камере"""
        for cam in self.cameras:
            if cam['index'] == camera_idx:
                return cam
        return None
    
    def list_cameras(self):
        """Список обнаруженных CSI камер"""
        return self.cameras
    
    def is_camera_available(self, camera_idx):
        """Проверить доступность CSI камеры"""
        for cam in self.cameras:
            if cam['index'] == camera_idx:
                return True
        return False

def create_csi_camera_manager(config, logger):
    """Создание экземпляра менеджера CSI камер"""
    return CSICameraManager(config, logger)

if __name__ == "__main__":
    # Тестовая функция
    print("🧪 Тестирование CSICameraManager")
    
    # Создаем минимальную конфигурацию
    class MockConfig:
        def get(self, key, default=None):
            return default
        def __getitem__(self, key):
            return {}
    
    class MockLogger:
        def log_info(self, msg): print(f"INFO: {msg}")
        def log_error(self, msg): print(f"ERROR: {msg}")
        def log_warning(self, msg): print(f"WARNING: {msg}")
    
    config = MockConfig()
    logger = MockLogger()
    
    manager = CSICameraManager(config, logger)
    
    if manager.cameras:
        print(f"\n📹 Найдено CSI камер: {len(manager.cameras)}")
        for cam in manager.cameras:
            print(f"  • {cam['name']} (индекс: {cam['index']})")
        
        # Пробуем открыть первую камеру
        print("\n🧪 Тест открытия камеры...")
        picam2 = manager.open_csi_camera(manager.cameras[0]['index'])
        
        if picam2:
            print("✅ Камера успешно открыта")
            print("🧪 Тест захвата кадра...")
            frame = manager.capture_frame()
            if frame is not None:
                print(f"✅ Кадр захвачен успешно. Размер: {frame.shape}")
            else:
                print("❌ Не удалось захватить кадр")
            
            manager.close_current()
    else:
        print("❌ CSI камеры не обнаружены")