#!/usr/bin/env python3
"""
Модуль для захвата фото с камер
"""

import os
import time
import threading
import cv2
import numpy as np
from picamera2 import Picamera2
from typing import Optional, Tuple, Dict, Any

class CameraCapture:
    """Класс для захвата фото с камер"""
    
    def __init__(self, camera_type: str = 'imx708', debug: bool = False):
        """
        Инициализация захвата камеры
        
        Args:
            camera_type: Тип камеры (imx708, imx415, ov5647)
            debug: Режим отладки
        """
        self.camera_type = camera_type
        self.debug = debug
        self.picam2 = None
        self.camera_info = None
        self.capture_size = None
        
        # Константы камер
        self.CAMERA_PROFILES = {
            'imx708': {
                'name': 'IMX708 (RPi Camera Module 3)',
                'full_resolution': (4608, 2592),
                'sensor_size': (4.55, 3.42),
                'pixel_size': 1.0,
                'focal_length': 3.04,
            },
            'imx415': {
                'name': 'Sony IMX415',
                'full_resolution': (3864, 2192),
                'sensor_size': (5.568, 3.132),
                'pixel_size': 1.45,
                'focal_length': 3.95,
            },
            'ov5647': {
                'name': 'OV5647 (RPi Camera Module v1/v2)',
                'full_resolution': (2592, 1944),
                'sensor_size': (3.68, 2.76),
                'pixel_size': 1.4,
                'focal_length': 3.6,
            }
        }
    
    def select_camera(self) -> bool:
        """Выбор камеры по типу"""
        if self.camera_type not in self.CAMERA_PROFILES:
            print(f"❌ Неизвестная камера: {self.camera_type}")
            return False
        
        self.camera_info = self.CAMERA_PROFILES[self.camera_type]
        
        # Пробуем разные индексы камер
        for i in range(3):
            try:
                temp_picam2 = Picamera2(i)
                
                # Получаем информацию о камере
                camera_properties = temp_picam2.camera_properties
                camera_name = camera_properties.get('Model', '')
                
                if self.debug:
                    print(f"🔍 Камера #{i}: {camera_name}")
                
                # Проверяем соответствие типу
                if self.camera_type == 'imx415' and 'imx415' in camera_name.lower():
                    print(f"✅ Найдена IMX415 (камера #{i})")
                    self.picam2 = temp_picam2
                    break
                elif self.camera_type == 'imx708' and 'imx708' in camera_name.lower():
                    print(f"✅ Найдена IMX708 (камера #{i})")
                    self.picam2 = temp_picam2
                    break
                elif self.camera_type == 'ov5647' and 'ov5647' in camera_name.lower():
                    print(f"✅ Найдена OV5647 (камера #{i})")
                    self.picam2 = temp_picam2
                    break
                else:
                    # Закрываем временную камеру
                    temp_picam2.close()
                    
            except Exception as e:
                if self.debug:
                    print(f"⚠️  Камера #{i}: {e}")
                if temp_picam2:
                    try:
                        temp_picam2.close()
                    except:
                        pass
                continue
        
        # Если не нашли по имени, используем первую доступную
        if self.picam2 is None:
            print("⚠️  Камера по типу не найдена, использую первую доступную")
            try:
                self.picam2 = Picamera2(0)
            except Exception as e:
                print(f"❌ Нет доступных камер: {e}")
                return False
        
        print(f"✅ Используется камера: {self.camera_info['name']}")
        return True
    
    def setup_camera(self, resolution: str = 'full', stream_width: int = 1280, stream_height: int = 720) -> bool:
        """Настройка камеры для съемки"""
        if self.picam2 is None:
            print("❌ Камера не инициализирована")
            return False
        
        try:
            # Определяем разрешение съемки
            if resolution == 'full':
                self.capture_size = self.camera_info['full_resolution']
                print(f"📸 Режим съемки: ПОЛНОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
            else:
                # Для стримового разрешения съемки используем стримовые параметры
                self.capture_size = (stream_width, stream_height)
                print(f"📸 Режим съемки: СТРИМОВОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
            
            # Конфигурация для съемки
            capture_config = self.picam2.create_still_configuration(
                main={
                    "size": self.capture_size,
                    "format": "RGB888"
                },
                controls={
                    "FrameRate": 5,
                    "AwbEnable": True,
                    "AeEnable": False,  # Фиксированная экспозиция для калибровки
                    "NoiseReductionMode": 2,  # Высокое качество для фото
                    "ExposureTime": 40000,  # 40ms
                    "AnalogueGain": 2.0,
                },
                buffer_count=4
            )
            
            self.picam2.stop()
            self.picam2.configure(capture_config)
            self.picam2.start()
            
            # Даем камере время на стабилизацию
            time.sleep(1.0)
            
            print(f"✅ Камера настроена на {self.capture_size[0]}x{self.capture_size[1]} для фото")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка настройки камеры: {e}")
            return False
    
    def capture_photo(self, save_dir: str = '003_pics', jpeg_quality: int = 95) -> Optional[str]:
        """Захват и сохранение фото"""
        if self.picam2 is None:
            print("❌ Камера не инициализирована")
            return None
        
        try:
            print(f"📸 Захват фото {self.capture_size[0]}x{self.capture_size[1]}...")
            
            # Захват кадра
            array = self.picam2.capture_array()
            
            if array is None or array.size == 0:
                print("❌ Не удалось захватить кадр")
                return None
            
            # Анализируем формат полученного кадра
            if len(array.shape) == 3:
                if array.shape[2] == 3:
                    # RGB формат
                    frame_rgb = array
                    print(f"📊 Формат фото: RGB, размер: {array.shape[1]}x{array.shape[0]}")
                elif array.shape[2] == 4:
                    # RGBA или RAW - конвертируем
                    print(f"⚠️  RAW формат: {array.shape[2]} канала, конвертирую...")
                    frame_rgb = array[:, :, :3]  # Берем первые 3 канала
                else:
                    print(f"⚠️  Неизвестный формат: {array.shape[2]} каналов")
                    frame_rgb = array
            else:
                # Монохромный
                print("⚠️  Монохромный формат, конвертирую в цветной...")
                frame_rgb = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)
            
            # Проверяем размер кадра
            height, width = frame_rgb.shape[:2]
            print(f"📐 Фактический размер кадра: {width}x{height}")
            
            # Проверяем экспозицию
            if len(frame_rgb.shape) == 3:
                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                avg_brightness = np.mean(gray)
                print(f"📊 Средняя яркость: {avg_brightness:.0f}/255")
            
            # Генерируем имя файла с помощью FileNamer
            filepath = generate_filename(
                camera_type=self.camera_type,
                save_dir=save_dir,
                timestamp=time.time()
            )
            
            filename = os.path.basename(filepath)
            
            # Сохраняем с высоким качеством
            # OpenCV ожидает BGR, но у нас RGB, конвертируем
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            cv2.imwrite(filepath, frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            
            # Проверяем файл
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath) / 1024
                print(f"✅ Сохранено: {filename}")
                print(f"   Размер файла: {file_size:.1f} КБ")
                print(f"   Размер изображения: {width}x{height}")
                return filename
            else:
                print(f"❌ Ошибка сохранения файла")
                return None
            
        except Exception as e:
            print(f"❌ Ошибка захвата фото: {e}")
            return None
    
    def capture_photo_with_delay(self, delay: float = 0, save_dir: str = '003_pics', jpeg_quality: int = 95) -> Optional[str]:
        """Захват фото с задержкой"""
        if delay > 0:
            print(f"⏱️  Съемка через {delay} сек...")
            for sec in range(int(delay), 0, -1):
                print(f"  {sec}...")
                time.sleep(1)
        
        print("📸 Съемка!")
        return self.capture_photo(save_dir, jpeg_quality)
    
    def cleanup(self):
        """Очистка ресурсов"""
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
            self.picam2 = None
        print("✅ Камера остановлена")

def capture_photo_interactive(camera_type: str = 'imx708', resolution: str = 'full', 
                             delay: float = 0, save_dir: str = '003_pics', 
                             jpeg_quality: int = 95, debug: bool = False) -> bool:
    """
    Интерактивная съемка фото с выбором камеры
    
    Args:
        camera_type: Тип камеры
        resolution: Разрешение ('full' или 'stream')
        delay: Задержка перед съемкой
        save_dir: Директория для сохранения
        jpeg_quality: Качество JPEG (1-100)
        debug: Режим отладки
    
    Returns:
        True если съемка прошла успешно, False в противном случае
    """
    capture = CameraCapture(camera_type, debug)
    
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
    """
    Съемка нескольких фото
    
    Args:
        camera_type: Тип камеры
        resolution: Разрешение ('full' или 'stream')
        count: Количество фото
        delay: Задержка перед съемкой
        save_dir: Директория для сохранения
        jpeg_quality: Качество JPEG (1-100)
        debug: Режим отладки
    
    Returns:
        Количество успешно сохраненных фото
    """
    capture = CameraCapture(camera_type, debug)
    
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
    """
    Съемка фото по нажатию клавиши
    
    Args:
        camera_type: Тип камеры
        resolution: Разрешение ('full' или 'stream')
        delay: Задержка перед съемкой
        save_dir: Директория для сохранения
        jpeg_quality: Качество JPEG (1-100)
        debug: Режим отладки
    
    Returns:
        True если съемка прошла успешно, False в противном случае
    """
    capture = CameraCapture(camera_type, debug)
    
    try:
        # Выбор камеры
        if not capture.select_camera():
            return False
        
        # Настройка камеры
        if not capture.setup_camera(resolution):
            return False
        
        captured_count = 0
        
        print(f"\n{'='*50}")
        print("📸 СЪЕМКА ФОТО ПО НАЖАТИЮ КЛАВИШИ")
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