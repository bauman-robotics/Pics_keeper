#!/usr/bin/env python3
"""
Модуль для захвата фото с веб-камеры через ffmpeg
"""

import os
import time
import subprocess
import cv2
import numpy as np
from typing import Optional
from utils.file_namer import generate_filename

class WebcamCapture:
    """Класс для захвата фото с веб-камеры через ffmpeg"""
    
    def __init__(self, camera_type: str = 'local_web', debug: bool = False):
        """
        Инициализация захвата веб-камеры
        
        Args:
            camera_type: Тип камеры (должен быть 'local_web')
            debug: Режим отладки
        """
        self.camera_type = camera_type
        self.debug = debug
        self.camera_info = {
            'name': 'Local Web Camera',
            'full_resolution': (1280, 960),
            'sensor_size': (3.2, 2.4),
            'pixel_size': 2.5,
            'focal_length': 3.6,
        }
        self.capture_size = (1280, 960)
    
    def check_ffmpeg(self) -> bool:
        """Проверка наличия ffmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if self.debug:
                    print("✅ ffmpeg доступен")
                return True
            else:
                print("❌ ffmpeg недоступен")
                return False
        except FileNotFoundError:
            print("❌ ffmpeg не установлен")
            return False
        except Exception as e:
            print(f"❌ Ошибка проверки ffmpeg: {e}")
            return False
    
    def check_webcam(self) -> bool:
        """Проверка доступности веб-камеры"""
        try:
            # Проверяем доступность /dev/video0
            if os.path.exists('/dev/video0'):
                if self.debug:
                    print("✅ Веб-камера доступна (/dev/video0)")
                return True
            else:
                print("❌ Веб-камера не найдена (/dev/video0)")
                return False
        except Exception as e:
            print(f"❌ Ошибка проверки веб-камеры: {e}")
            return False
    
    def get_supported_resolutions(self) -> list:
        """Получение поддерживаемых разрешений веб-камеры"""
        try:
            # Получаем информацию о веб-камере
            result = subprocess.run([
                'ffmpeg', '-f', 'v4l2', '-list_formats', 'all', '-i', '/dev/video0'
            ], capture_output=True, text=True, timeout=10)
            
            resolutions = []
            if result.returncode == 0:
                output = result.stderr  # Информация выводится в stderr
                lines = output.split('\n')
                
                for line in lines:
                    if 'Size: ' in line:
                        # Ищем строки вида: Size: 1280x720
                        parts = line.split()
                        for part in parts:
                            if 'x' in part and part.replace('x', '').isdigit():
                                try:
                                    width, height = map(int, part.split('x'))
                                    resolutions.append((width, height))
                                except:
                                    pass
            
            if self.debug:
                print(f"📊 Поддерживаемые разрешения: {resolutions}")
            
            return resolutions
            
        except Exception as e:
            if self.debug:
                print(f"⚠️  Не удалось получить разрешения: {e}")
            return []
    
    def select_camera(self) -> bool:
        """Проверка и выбор веб-камеры"""
        if self.camera_type != 'local_web':
            print(f"❌ Неверный тип камеры для веб-камеры: {self.camera_type}")
            return False
        
        # Проверяем ffmpeg
        if not self.check_ffmpeg():
            return False
        
        # Проверяем веб-камеру
        if not self.check_webcam():
            return False
        
        print(f"✅ Используется веб-камера: {self.camera_info['name']}")
        
        # Показываем поддерживаемые разрешения
        resolutions = self.get_supported_resolutions()
        if resolutions:
            print(f"📊 Доступные разрешения: {resolutions}")
        
        return True
    
    def setup_camera(self, resolution: str = 'full', stream_width: int = 1280, stream_height: int = 720) -> bool:
        """Настройка веб-камеры"""
        if resolution == 'full':
            self.capture_size = self.camera_info['full_resolution']
            print(f"📸 Режим съемки: ПОЛНОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
        else:
            # Для стримового разрешения используем указанные параметры
            self.capture_size = (stream_width, stream_height)
            print(f"📸 Режим съемки: СТРИМОВОЕ РАЗРЕШЕНИЕ ({self.capture_size[0]}x{self.capture_size[1]})")
        
        print(f"✅ Веб-камера настроена на {self.capture_size[0]}x{self.capture_size[1]} для фото")
        return True
    
    def capture_photo(self, save_dir: str = '003_pics', jpeg_quality: int = 95) -> Optional[str]:
        """Захват и сохранение фото через ffmpeg"""
        if not self.check_ffmpeg():
            print("❌ ffmpeg недоступен для захвата")
            return None
        
        try:
            print(f"📸 Захват фото {self.capture_size[0]}x{self.capture_size[1]} через ffmpeg...")
            
            # Преобразуем относительный путь в абсолютный
            if not os.path.isabs(save_dir):
                # Определяем базовую директорию (где находится main.py)
                import inspect
                frame = inspect.currentframe()
                try:
                    # Идем вверх по стеку, пока не найдем main.py
                    while frame:
                        filename = frame.f_code.co_filename
                        if filename.endswith('main.py'):
                            base_dir = os.path.dirname(os.path.abspath(filename))
                            project_root = os.path.dirname(base_dir)
                            break
                        frame = frame.f_back
                    else:
                        # Если не нашли main.py, используем текущую директорию
                        project_root = os.getcwd()
                finally:
                    del frame
                
                save_dir = os.path.join(project_root, save_dir)
            
            # Генерируем имя файла с помощью FileNamer
            filepath = generate_filename(
                camera_type=self.camera_type,
                save_dir=save_dir,
                timestamp=time.time()
            )
            
            filename = os.path.basename(filepath)
            
            # Команда ffmpeg для захвата одного кадра
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'v4l2',                    # Формат ввода
                '-video_size', f'{self.capture_size[0]}x{self.capture_size[1]}',  # Размер видео
                '-i', '/dev/video0',             # Источник видео
                '-frames', '1',                  # Количество кадров
                '-q:v', str(max(1, min(100, 100 - jpeg_quality))),  # Качество (чем меньше, тем выше качество)
                '-y',                            # Перезапись без подтверждения
                filepath                         # Выходной файл
            ]
            
            if self.debug:
                print(f"🎬 Команда ffmpeg: {' '.join(ffmpeg_cmd)}")
            
            # Выполняем команду
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Проверяем файл
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath) / 1024
                    print(f"✅ Сохранено: {filename}")
                    print(f"   Размер файла: {file_size:.1f} КБ")
                    print(f"   Размер изображения: {self.capture_size[0]}x{self.capture_size[1]}")
                    
                    # Проверяем качество изображения
                    try:
                        img = cv2.imread(filepath)
                        if img is not None:
                            height, width = img.shape[:2]
                            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                            avg_brightness = np.mean(gray)
                            print(f"   Фактический размер: {width}x{height}")
                            print(f"   Средняя яркость: {avg_brightness:.0f}/255")
                        else:
                            print("⚠️  Не удалось прочитать изображение для анализа")
                    except Exception as e:
                        print(f"⚠️  Ошибка анализа изображения: {e}")
                    
                    return filename
                else:
                    print(f"❌ Файл не создан")
            else:
                print(f"❌ Ошибка ffmpeg: {result.stderr}")
                if self.debug:
                    print(f"   stdout: {result.stdout}")
                    print(f"   stderr: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            print("❌ Таймаут ffmpeg")
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
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Захват одного кадра для стрима"""
        if not self.check_ffmpeg():
            return None
        
        try:
            # Временный файл для захвата кадра
            temp_file = '/tmp/webcam_frame.jpg'
            
            # Команда ffmpeg для захвата одного кадра
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'v4l2',
                '-video_size', f'{self.capture_size[0]}x{self.capture_size[1]}',
                '-i', '/dev/video0',
                '-frames', '1',
                '-q:v', '2',  # Высокое качество для стрима
                '-y',
                temp_file
            ]
            
            # Выполняем команду
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                # Читаем изображение
                frame = cv2.imread(temp_file)
                
                # Удаляем временный файл
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                if frame is not None:
                    return frame
            
        except Exception as e:
            if self.debug:
                print(f"❌ Ошибка захвата кадра: {e}")
        
        return None
    
    def initialize(self) -> bool:
        """Инициализация веб-камеры"""
        return self.select_camera()
    
    def cleanup(self):
        """Очистка ресурсов"""
        print("✅ Веб-камера остановлена")

def capture_photo_interactive(camera_type: str = 'local_web', resolution: str = 'full', 
                             delay: float = 0, save_dir: str = '003_pics', 
                             jpeg_quality: int = 95, debug: bool = False) -> bool:
    """Интерактивная съемка фото с веб-камеры"""
    capture = WebcamCapture(camera_type, debug)
    
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

def capture_multiple_photos(camera_type: str = 'local_web', resolution: str = 'full',
                           count: int = 20, delay: float = 0, save_dir: str = '003_pics',
                           jpeg_quality: int = 95, debug: bool = False) -> int:
    """Съемка нескольких фото с веб-камеры"""
    capture = WebcamCapture(camera_type, debug)
    
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

def capture_photo_by_keypress(camera_type: str = 'local_web', resolution: str = 'full',
                             delay: float = 0, save_dir: str = '003_pics',
                             jpeg_quality: int = 95, debug: bool = False) -> bool:
    """Съемка фото по нажатию клавиши с веб-камеры"""
    capture = WebcamCapture(camera_type, debug)
    
    try:
        # Выбор камеры
        if not capture.select_camera():
            return False
        
        # Настройка камеры
        if not capture.setup_camera(resolution):
            return False
        
        captured_count = 0
        
        print(f"\n{'='*50}")
        print("📸 СЪЕМКА ФОТО ПО НАЖАТИЮ КЛАВИШИ (ВЕБ-КАМЕРА)")
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