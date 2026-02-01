
'''
Посмотрите устройства V4L2
v4l2-ctl --list-devices

# Проверка всех V4L2 устройств с деталями
v4l2-ctl --list-devices

# Проверка форматов для конкретного устройства CSI
v4l2-ctl --device=/dev/video6 --list-formats-ext

# Проверка камеры через vcgencmd
vcgencmd get_camera

# Тест CSI камеры через libcamera
libcamera-still -o test_csi.jpg --nopreview

# Тест CSI камеры через V4L2 (если поддерживается)
fswebcam -d /dev/video6 test_v4l2.jpg

Установка PIL для информации об изображениях:
pip install Pillow


source /home/pi/projects/Hailo8_projects/cam_calibr/venv/bin/activate

'''

import cv2
import warnings
import sys
import os
import time
import signal
import subprocess
import re
from datetime import datetime

# Проверяем наличие picamera2
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("⚠️  Picamera2 не установлен. CSI камеры могут не работать.")
    print("   Установите: pip install picamera2")

class CameraCaptureSSH:
    def __init__(self):
        self.running = True
        self.camera_index = None
        self.cap = None
        self.camera_type = None
        self.picam2 = None
        
        # Настройка обработки Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Обработчик Ctrl+C"""
        print("\n\nЗавершение работы...")
        self.running = False
        
        # Закрываем все камеры
        if self.cap is not None:
            self.cap.release()
        if self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
        
        sys.exit(0)
    
    def detect_all_cameras(self):
        """Обнаруживает ВСЕ камеры"""
        print("\n" + "="*50)
        print("ОБНАРУЖЕНИЕ ВСЕХ КАМЕР...")
        print("="*50)
        
        all_cameras = []
        
        # 1. Сначала ищем USB камеры через V4L2
        print("\nПоиск USB камер...")
        usb_cameras = self.detect_usb_cameras()
        all_cameras.extend(usb_cameras)
        
        # 2. Проверяем наличие CSI камер через Picamera2
        print("\nПоиск CSI камер...")
        csi_cameras = self.detect_csi_cameras()
        all_cameras.extend(csi_cameras)
        
        return all_cameras
    
    def detect_usb_cameras(self):
        """Обнаруживает USB камеры через V4L2"""
        usb_cameras = []
        
        # Подавляем предупреждения
        warnings.filterwarnings('ignore')
        original_stderr = sys.stderr
        
        try:
            sys.stderr = open(os.devnull, 'w')
            
            # Проверяем только первые 10 устройств
            for i in range(10):
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                    if cap.isOpened():
                        # Пробуем получить кадр
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            # Получаем название устройства
                            device_name = self.get_device_name(i)
                            
                            # Фильтруем только USB камеры
                            if any(x in device_name.lower() for x in ['usb', 'camera', 'webcam', 'hd camera']):
                                usb_cameras.append({
                                    'index': i,
                                    'device': f'/dev/video{i}',
                                    'name': device_name,
                                    'width': width,
                                    'height': height,
                                    'fps': fps if fps > 0 else 'N/A',
                                    'type': 'USB',
                                    'method': 'v4l2',
                                    'open_func': self.open_usb_camera
                                })
                                print(f"  ✓ USB камера: /dev/video{i} - {device_name}")
                            else:
                                print(f"  ⚠️  Не USB: /dev/video{i} - {device_name}")
                        cap.release()
                except Exception as e:
                    continue
            
            return usb_cameras
            
        finally:
            sys.stderr = original_stderr
    
    def get_device_name(self, device_index):
        """Получает название устройства V4L2"""
        try:
            # Пробуем получить через v4l2-ctl
            cmd = f"v4l2-ctl --device=/dev/video{device_index} --info 2>/dev/null | grep 'Card type'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout:
                match = re.search(r'Card type\s*:\s*(.+)', result.stdout)
                if match:
                    return match.group(1).strip()
            
            # Альтернативный способ
            cmd = f"cat /sys/class/video4linux/video{device_index}/name 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
        except:
            pass
        
        return f"Unknown Device {device_index}"
    
    def detect_csi_cameras(self):
        """Обнаруживает CSI камеры через Picamera2"""
        csi_cameras = []
        
        if not PICAMERA2_AVAILABLE:
            print("  ✗ Picamera2 не установлен")
            print("  Установите: pip install picamera2")
            return csi_cameras
        
        print("  Проверка наличия Picamera2...")
        
        try:
            # Пробуем обнаружить камеры через Picamera2
            print("  Ищу CSI камеры через Picamera2...")
            
            # Проверяем доступные камеры
            # Picamera2 поддерживает несколько камер через индекс
            for cam_idx in range(2):  # Проверяем до 2 камер
                try:
                    print(f"    Проверка камеры #{cam_idx}...", end=' ', flush=True)
                    
                    picam2 = Picamera2(cam_idx)
                    
                    # Пробуем получить информацию о камере
                    camera_properties = picam2.camera_properties
                    
                    if camera_properties:
                        model = camera_properties.get('Model', 'Unknown CSI Camera')
                        print(f"✓ найдена: {model}")
                        
                        # Пробуем получить доступные разрешения
                        config = picam2.create_still_configuration()
                        
                        csi_cameras.append({
                            'index': cam_idx,
                            'device': f'CSI Camera {cam_idx}',
                            'name': f'{model} (Picamera2)',
                            'width': 4608,  # Максимальное для IMX708
                            'height': 2592,
                            'fps': 10,
                            'type': 'CSI',
                            'method': 'picamera2',
                            'open_func': self.open_picamera2,
                            'camera_idx': cam_idx
                        })
                        
                        picam2.close()
                    else:
                        print("✗ нет камеры")
                        picam2.close()
                        break  # Больше нет камер
                        
                except Exception as e:
                    print(f"✗ ошибка: {str(e)[:30]}")
                    if cam_idx == 0:
                        # На первой камере должна быть ошибка если нет камеры
                        print("  Вероятно, CSI камера не подключена или не включена")
                        break
        
        except Exception as e:
            print(f"  Ошибка Picamera2: {e}")
        
        return csi_cameras
    
    def open_usb_camera(self, camera_info):
        """Открывает USB камеру"""
        try:
            self.cap = cv2.VideoCapture(camera_info['index'], cv2.CAP_V4L2)
            if not self.cap.isOpened():
                print(f"✗ Не удалось открыть /dev/video{camera_info['index']}")
                return False
            
            # Устанавливаем максимальное доступное разрешение
            resolutions = [
                (1920, 1080),
                (1280, 720),
                (640, 480)
            ]
            
            for width, height in resolutions:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                time.sleep(0.1)
                
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if actual_width == width and actual_height == height:
                    print(f"  Установлено разрешение: {width}x{height}")
                    break
            
            # Очищаем буфер
            for _ in range(5):
                self.cap.read()
            
            return True
            
        except Exception as e:
            print(f"✗ Ошибка открытия USB камеры: {e}")
            return False
    
    def open_picamera2(self, camera_info):
        """Открывает CSI камеру через Picamera2"""
        if not PICAMERA2_AVAILABLE:
            print("✗ Picamera2 не установлен")
            return False
        
        try:
            camera_idx = camera_info.get('camera_idx', 0)
            self.picam2 = Picamera2(camera_idx)
            
            # Создаем конфигурацию для фото
            config = self.picam2.create_still_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                controls={"FrameRate": 10, "AwbEnable": True}
            )
            
            self.picam2.configure(config)
            self.picam2.start()
            
            # Даем камере время на инициализацию
            time.sleep(1.5)
            
            print("  CSI камера инициализирована через Picamera2")
            return True
            
        except Exception as e:
            print(f"✗ Ошибка открытия CSI камеры: {e}")
            return False
    
    def capture_image(self, camera_info):
        """Захватывает изображение с выбранной камеры"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        print(f"\nЗахват с камеры: {camera_info['name']}")
        print(f"Метод: {camera_info['method'].upper()}")
        
        # Открываем камеру
        if not camera_info['open_func'](camera_info):
            return False
        
        try:
            if camera_info['method'] == 'picamera2':
                return self.capture_picamera2(camera_info, timestamp)
            else:  # v4l2
                return self.capture_v4l2(camera_info, timestamp)
                
        finally:
            # Закрываем камеру
            self.close_camera(camera_info['method'])

    def capture_picamera2(self, camera_info, timestamp):
        """Захват через Picamera2"""
        # Создаем папку если не существует
        base_dir = "captured_photos"
        os.makedirs(base_dir, exist_ok=True)
        
        # Генерируем имя файла
        # Формат: csi_picamera2_камера_дата_время.jpg
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"csi_picamera2_{camera_info.get('camera_idx', 0)}_{date_str}.jpg"
        filepath = os.path.join(base_dir, filename)
        
        print(f"  Сохраняю в: {filepath}")
        
        try:
            # Захватываем изображение
            print("  Захват кадра...")
            array = self.picam2.capture_array()
            
            print(f"  📊 Массив: shape={array.shape}, dtype={array.dtype}")
            
            # Проверяем формат и конвертируем если нужно
            if len(array.shape) == 3:
                if array.shape[2] == 3:
                    # Picamera2 возвращает RGB, OpenCV хочет BGR
                    print("  Конвертируем RGB → BGR...")
                    image_bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                    
                    # Сохраняем
                    cv2.imwrite(filepath, image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                elif array.shape[2] == 4:
                    # RGBA формат
                    print("  Конвертируем RGBA → BGR...")
                    image_rgb = cv2.cvtColor(array, cv2.COLOR_RGBA2RGB)
                    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                    cv2.imwrite(filepath, image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                else:
                    print(f"  ⚠️ Неизвестный формат с {array.shape[2]} каналами")
                    cv2.imwrite(filepath, array)
            else:
                # Монохромное изображение
                cv2.imwrite(filepath, array)
            
            # Проверяем результат
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath) / 1024
                print(f"\n✓ Снимок сохранен: {filepath}")
                print(f"  Размер файла: {file_size:.1f} KB")
                
                # Показываем информацию об изображении
                img = cv2.imread(filepath)
                if img is not None:
                    print(f"  Размер изображения: {img.shape[1]}x{img.shape[0]}")
                    print(f"  Каналы: {img.shape[2]}")
                
                return True
            else:
                print("✗ Файл не создан")
                return False
                
        except Exception as e:
            print(f"✗ Ошибка при захвате: {e}")
            import traceback
            traceback.print_exc()
            return False

    def capture_v4l2(self, camera_info, timestamp):
        """Захват через V4L2"""
        # Создаем папку если не существует
        base_dir = "captured_photos"
        os.makedirs(base_dir, exist_ok=True)
        
        # Генерируем имя файла
        # Формат: usb_video0_дата_время.jpg или csi_video6_дата_время.jpg
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if camera_info['type'] == 'CSI':
            filename = f"csi_video{camera_info['index']}_{date_str}.jpg"
            prefix = "CSI"
        else:
            filename = f"usb_video{camera_info['index']}_{date_str}.jpg"
            prefix = "USB"
        
        filepath = os.path.join(base_dir, filename)
        
        print(f"  Использую V4L2 для {prefix} камеры...")
        print(f"  Сохраняю в: {filepath}")
        
        try:
            # Подавляем предупреждения
            original_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')
            warnings.filterwarnings('ignore')
            
            # Захватываем кадр
            ret, frame = self.cap.read()
            
            sys.stderr = original_stderr
            
            if not ret or frame is None:
                print("✗ Не удалось получить кадр")
                return False
            
            # Сохраняем
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath) / 1024
                print(f"\n✓ Снимок сохранен: {filepath}")
                print(f"  Размер файла: {file_size:.1f} KB")
                print(f"  Размер изображения: {frame.shape[1]}x{frame.shape[0]}")
                return True
            else:
                print("✗ Файл не создан")
                return False
                
        except Exception as e:
            print(f"✗ Ошибка при захвате: {e}")
            return False
    
    def close_camera(self, method):
        """Закрывает камеру"""
        try:
            if method == 'picamera2' and self.picam2 is not None:
                self.picam2.stop()
                self.picam2.close()
                self.picam2 = None
                print("  CSI камера закрыта")
            elif method == 'v4l2' and self.cap is not None:
                self.cap.release()
                self.cap = None
                print("  USB камера закрыта")
        except:
            pass
    
    def run(self):
        """Основной цикл программы"""
        print("\n" + "="*60)
        print("ПРОГРАММА ЗАХВАТА С КАМЕР")
        print("="*60)
        print("Поддерживаемые камеры:")
        print("  • USB камеры - через V4L2/OpenCV")
        print("  • CSI камеры - через Picamera2 (требует установки)")
        print("="*60)
        
        # Обнаруживаем все камеры
        cameras = self.detect_all_cameras()
        
        if not cameras:
            print("\n✗ Камеры не обнаружены!")
            print("\nРекомендации:")
            print("  1. Для CSI камер:")
            print("     - Установите: pip install picamera2")
            print("     - Включите камеру: sudo raspi-config")
            print("     - Перезагрузите: sudo reboot")
            print("  2. Для USB камер:")
            print("     - Проверьте подключение")
            print("     - Попробуйте: lsusb")
            return
        
        print(f"\nОбнаружено камер: {len(cameras)}")
        
        while self.running:
            # Показываем меню
            print("\n" + "="*60)
            print("ВЫБЕРИТЕ КАМЕРУ:")
            print("="*60)
            
            for i, cam in enumerate(cameras, 1):
                if cam['type'] == 'CSI':
                    device_info = cam['device']
                    type_marker = "[CSI]"
                else:
                    device_info = f"/dev/video{cam['index']}"
                    type_marker = "[USB]"
                
                print(f"  {i:2}. {type_marker:6} {device_info:20} - {cam['name'][:30]}")
                print(f"       Разрешение: {cam['width']}x{cam['height']}, FPS: {cam['fps']}")
                print(f"       Метод: {cam['method'].upper()}")
            
            print("\n" + "="*60)
            
            # Получаем выбор пользователя
            try:
                choice = input("\nВыберите камеру (1-9) или 'q' для выхода: ").strip().lower()
                
                if choice == 'q':
                    print("\nВыход...")
                    break
                
                if choice.isdigit():
                    cam_num = int(choice)
                    
                    if 1 <= cam_num <= len(cameras):
                        selected_cam = cameras[cam_num - 1]
                        
                        # Захватываем изображение
                        print(f"\n{'='*60}")
                        print(f"ЗАХВАТ С КАМЕРЫ #{cam_num}")
                        print(f"{'='*60}")
                        
                        if self.capture_image(selected_cam):
                            print("\n✓ Успешно!")
                        else:
                            print("\n✗ Ошибка захвата")
                        
                        # # Спрашиваем о продолжении
                        # again = input("\nСделать еще снимок? (y/n): ").strip().lower()
                        # if again != 'y':
                        #     print("\nЗавершение работы...")
                        #     break
                    else:
                        print(f"\nОшибка: выберите число от 1 до {len(cameras)}")
                else:
                    print("\nОшибка: введите номер камеры или 'q'")
                    
            except KeyboardInterrupt:
                print("\n\nЗавершено по Ctrl+C")
                break
            except Exception as e:
                print(f"\nОшибка: {e}")
                continue
        
        print("\nПрограмма завершена.")

def check_dependencies():
    """Проверяет зависимости"""
    print("🔍 Проверка зависимостей...")
    
    # Проверяем OpenCV
    try:
        import cv2
        cv2_version = cv2.__version__
        print(f"✓ OpenCV: {cv2_version}")
    except ImportError:
        print("✗ OpenCV не установлен")
        print("  Установите: sudo apt install python3-opencv")
        return False
    
    # Проверяем Picamera2
    if not PICAMERA2_AVAILABLE:
        print("⚠️  Picamera2 не установлен (CSI камеры могут не работать)")
        print("  Установите: pip install picamera2")
    
    # Проверяем v4l-utils для информации об устройствах
    try:
        result = subprocess.run("which v4l2-ctl", shell=True, 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ v4l2-ctl доступен")
        else:
            print("⚠️  v4l2-ctl не найден (информация об устройствах может быть ограничена)")
            print("  Установите: sudo apt install v4l-utils")
    except:
        pass
    
    return True

def main():
    """Точка входа"""
    if not check_dependencies():
        print("\n⚠️  Некоторые зависимости отсутствуют")
        response = input("Продолжить? (y/n): ").strip().lower()
        if response != 'y':
            print("Выход...")
            return
    
    # Проверяем, что мы на Raspberry Pi
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            if 'Raspberry Pi' in model:
                print(f"\n📱 Обнаружена: {model.strip()}")
            else:
                print("\n⚠️  Внимание: Возможно, это не Raspberry Pi")
    except:
        print("\n⚠️  Не удалось определить модель устройства")
    
    # Запускаем приложение
    app = CameraCaptureSSH()
    app.run()

if __name__ == "__main__":
    main()