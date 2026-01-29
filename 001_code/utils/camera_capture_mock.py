#!/usr/bin/env python3
"""
Заглушка для модуля захвата фото (для систем без камер)
"""

import os
import time
import random
from typing import Optional
from utils.file_namer import generate_filename

class MockCameraCapture:
    """Заглушка камеры для тестирования"""
    
    def __init__(self, camera_type: str = 'imx708', debug: bool = False):
        self.camera_type = camera_type
        self.debug = debug
        self.camera_info = {
            'name': f'Mock Camera {camera_type}',
            'full_resolution': (4608, 2592)
        }
        self.capture_size = (4608, 2592)
    
    def select_camera(self) -> bool:
        """Имитация выбора камеры"""
        print(f"✅ Используется заглушка камеры: {self.camera_info['name']}")
        return True
    
    def setup_camera(self, resolution: str = 'full', stream_width: int = 1280, stream_height: int = 720) -> bool:
        """Имитация настройки камеры"""
        if resolution == 'full':
            self.capture_size = self.camera_info['full_resolution']
            print(f"📸 Режим съемки: ПОЛНОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
        else:
            self.capture_size = (stream_width, stream_height)
            print(f"📸 Режим съемки: СТРИМОВОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
        
        print(f"✅ Камера настроена на {self.capture_size[0]}x{self.capture_size[1]} для фото")
        return True
    
    def capture_photo(self, save_dir: str = '003_pics', jpeg_quality: int = 95) -> Optional[str]:
        """Имитация захвата фото"""
        print(f"📸 Имитация захвата фото {self.capture_size[0]}x{self.capture_size[1]}...")
        
        # Имитация задержки захвата
        time.sleep(0.5)
        
        # Генерируем имя файла с помощью FileNamer
        filepath = generate_filename(
            camera_type=self.camera_type,
            save_dir=save_dir,
            timestamp=time.time()
        )
        
        filename = os.path.basename(filepath)
        
        # Создаем пустой файл (имитация сохранения)
        with open(filepath, 'w') as f:
            f.write(f"Mock photo: {filename}\n")
            f.write(f"Resolution: {self.capture_size[0]}x{self.capture_size[1]}\n")
            f.write(f"Quality: {jpeg_quality}\n")
            f.write(f"Timestamp: {int(time.time())}\n")
        
        # Имитация проверки файла
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath) / 1024
            print(f"✅ Сохранено: {filename}")
            print(f"   Размер файла: {file_size:.1f} КБ")
            print(f"   Размер изображения: {self.capture_size[0]}x{self.capture_size[1]}")
            return filename
        else:
            print(f"❌ Ошибка сохранения файла")
            return None
    
    def capture_photo_with_delay(self, delay: float = 0, save_dir: str = '003_pics', jpeg_quality: int = 95) -> Optional[str]:
        """Имитация захвата фото с задержкой"""
        if delay > 0:
            print(f"⏱️  Съемка через {delay} сек...")
            for sec in range(int(delay), 0, -1):
                print(f"  {sec}...")
                time.sleep(1)
        
        print("📸 Съемка!")
        return self.capture_photo(save_dir, jpeg_quality)
    
    def cleanup(self):
        """Очистка ресурсов"""
        print("✅ Заглушка камеры остановлена")

def capture_photo_interactive(camera_type: str = 'imx708', resolution: str = 'full', 
                             delay: float = 0, save_dir: str = '003_pics', 
                             jpeg_quality: int = 95, debug: bool = False) -> bool:
    """Имитация интерактивной съемки фото"""
    capture = MockCameraCapture(camera_type, debug)
    
    try:
        # Выбор камеры
        if not capture.select_camera():
            return False
        
        # Настройка камеры
        if not capture.setup_camera(resolution):
            return False
        
        # Захват фото
        filename = capture.capture_photo_with_delay(delay, save_dir, jpeg_quality)
        
        if filename:
            print(f"✅ Снимок сохранен: {filename}")
            return True
        else:
            print("❌ Не удалось сохранить снимок")
            return False
            
    except KeyboardInterrupt:
        print("\n🛑 Съемка прервана")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        capture.cleanup()

def capture_multiple_photos(camera_type: str = 'imx708', resolution: str = 'full',
                           count: int = 20, delay: float = 0, save_dir: str = '003_pics',
                           jpeg_quality: int = 95, debug: bool = False) -> int:
    """Имитация съемки нескольких фото"""
    capture = MockCameraCapture(camera_type, debug)
    
    try:
        # Выбор камеры
        if not capture.select_camera():
            return 0
        
        # Настройка камеры
        if not capture.setup_camera(resolution):
            return 0
        
        captured_count = 0
        
        for i in range(count):
            print(f"\n{'='*50}")
            print(f"📸 СНИМОК {i+1}/{count} (сохранено: {captured_count})")
            print(f"{'='*50}")
            
            # Захват фото
            filename = capture.capture_photo_with_delay(delay, save_dir, jpeg_quality)
            
            if filename:
                captured_count += 1
                print(f"✅ Снимок #{captured_count} сохранен: {filename}")
            else:
                print("❌ Не удалось сохранить снимок")
        
        print(f"\n✅ Съемка завершена! Сохранено снимков: {captured_count}/{count}")
        return captured_count
        
    except KeyboardInterrupt:
        print("\n🛑 Съемка прервана")
        return captured_count
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return captured_count
    finally:
        capture.cleanup()

def capture_photo_by_keypress(camera_type: str = 'imx708', resolution: str = 'full',
                             delay: float = 0, save_dir: str = '003_pics',
                             jpeg_quality: int = 95, debug: bool = False) -> bool:
    """Имитация съемки фото по нажатию клавиши"""
    capture = MockCameraCapture(camera_type, debug)
    
    try:
        # Выбор камеры
        if not capture.select_camera():
            return False
        
        # Настройка камеры
        if not capture.setup_camera(resolution):
            return False
        
        captured_count = 0
        
        print(f"\n{'='*50}")
        print("📸 СЪЕМКА ФОТО ПО НАЖАТИЮ КЛАВИШИ (ЗАГЛУШКА)")
        print(f"{'='*50}")
        print(f"Камера: {capture.camera_info['name']}")
        print(f"Разрешение: {capture.capture_size[0]}x{capture.capture_size[1]}")
        print(f"Директория: {save_dir}")
        print(f"{'='*50}")
        
        while True:
            print(f"\nКоманды:")
            print("  [Enter] - сделать снимок")
            print("  [s]     - пропустить")
            print("  [q]     - завершить")
            
            choice = input("\nВыбор [Enter/s/q]: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 's':
                continue
            
            # Основной снимок
            print(f"\n⏱️  Съемка через {delay} сек...")
            for sec in range(int(delay), 0, -1):
                print(f"  {sec}...")
                time.sleep(1)
            
            print("📸 Съемка!")
            
            # Захват и сохранение фото
            filename = capture.capture_photo(save_dir, jpeg_quality)
            
            if filename:
                captured_count += 1
                print(f"✅ Снимок #{captured_count} сохранен: {filename}")
            else:
                print("❌ Не удалось сохранить снимок")
        
        print(f"\n✅ Съемка завершена! Сохранено снимков: {captured_count}")
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 Съемка прервана")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        capture.cleanup()