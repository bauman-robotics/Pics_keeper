
import cv2

# Пробуем импортировать CSI Camera Manager
try:
    from csi_camera_manager import CSICameraManager
    PICAMERA2_AVAILABLE = True
    print("✅ CSICameraManager загружен успешно")
except ImportError as e:
    print(f"⚠️  Не удалось загрузить CSICameraManager: {e}")
    print("   Установите: pip install picamera2")
    print("   Или проверьте наличие файла utils_rpi/csi_camera_manager.py")
    PICAMERA2_AVAILABLE = False
    CSICameraManager = None

try:
    from picamera2 import Picamera2    
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("⚠️  Picamera2 не установлен. CSI камеры не будут доступны.")
    print("   Установите: pip install picamera2")

# ===============================================================
# not used 
def get_camera_backend(backend_name):
    """Получение бэкенда OpenCV по имени"""
    backends = {
        "default": None,
        "v4l2": cv2.CAP_V4L2,
        "ffmpeg": cv2.CAP_FFMPEG,
        "direct": cv2.CAP_V4L2  # Для прямого доступа используем V4L2
    }
    return backends.get(backend_name.lower(), None)

# ===============================================================

def test_camera_backends(config, logger):
    """Тестируем разные способы открытия камеры согласно конфигурации"""
    
    camera_config = config['camera']
    backend_mode = camera_config['backend'].lower()
    is_raspberry_pi = config.get('raspberry_pi', False)
    
    # Получаем device как строку
    device_value = camera_config['device']
    device_str = str(device_value)  # Конвертируем в строку
    
    # Если на Raspberry Pi и доступен Picamera2, пробуем CSI камеры
    if is_raspberry_pi and PICAMERA2_AVAILABLE:
        print("\n=== Проверка CSI камер через Picamera2 ===")
        
        csi_manager = CSICameraManager(config, logger)
        csi_cameras = csi_manager.cameras
        
        if csi_cameras:
            print(f"✅ Найдено CSI камер: {len(csi_cameras)}")
            for cam in csi_cameras:
                print(f"  • {cam['name']}")
            
            # Если в конфиге указана CSI камера, используем её
            if device_str.startswith('csi_'):  # Используем строку!
                try:
                    camera_idx = int(device_str.split('_')[1])
                    picam2 = csi_manager.open_csi_camera(camera_idx)
                    if picam2:
                        print(f"✅ Используем CSI камеру #{camera_idx}")
                        # Возвращаем словарь с информацией о типе камеры
                        return {'type': 'csi', 'csi_manager': csi_manager, 'picam2': picam2}
                except (ValueError, IndexError) as e:
                    print(f"⚠️  Ошибка парсинга CSI индекса: {e}")
                except Exception as e:
                    print(f"⚠️  Ошибка открытия CSI камеры: {e}")
    
    # Остальная логика для USB камер через V4L2
    print(f"\n=== Тестирование камеры: устройство {device_str} ===")
    
    if backend_mode == "auto":
        # Автоматическое тестирование бэкендов
        backends = []
        
        # Если Raspberry Pi - пробуем оптимизированные варианты
        if is_raspberry_pi:
            logger.info("Обнаружен Raspberry Pi - применяю специальные настройки")
            
            # Пробуем разные варианты
            for backend_name in camera_config['test_backends']:
                if backend_name == "default":
                    backends.append((f"Default", device_value, cv2.CAP_ANY))
                
                elif backend_name == "rpi_v4l2":
                    backends.append((f"V4L2", device_value, cv2.CAP_V4L2))
                
                elif backend_name.startswith("direct_video"):
                    # Извлекаем номер из имени, например "direct_video0" -> 0
                    try:
                        video_num = int(backend_name.replace("direct_video", ""))
                        backends.append((f"Direct /dev/video{video_num}", f"/dev/video{video_num}", cv2.CAP_V4L2))
                    except:
                        pass
                
                elif backend_name == "picamera2":
                    # Уже обработали выше
                    continue
        
        # Тестируем все бэкенды
        successful_cam = None
        
        for name, device, backend in backends:
            print(f"\n=== Тестируем {name} ===")
            logger.info(f"Тестируем подключение камеры: {name}")
            
            try:
                # Даем время на инициализацию
                if is_raspberry_pi:
                    import time
                    time.sleep(0.3)
                
                if backend is None:
                    cam = cv2.VideoCapture(device)
                else:
                    cam = cv2.VideoCapture(device, backend)
                
                # Настройки для Raspberry Pi
                if is_raspberry_pi:
                    time.sleep(0.2)
                    
                    # Устанавливаем буфер
                    try:
                        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except:
                        pass
                
                # Устанавливаем разрешение если указано
                if 'width' in camera_config and 'height' in camera_config:
                    cam.set(cv2.CAP_PROP_FRAME_WIDTH, camera_config['width'])
                    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_config['height'])
                    # На RPi даем время на изменение разрешения
                    if is_raspberry_pi:
                        time.sleep(0.1)
                
                # Устанавливаем FPS если указано
                if 'fps' in camera_config:
                    cam.set(cv2.CAP_PROP_FPS, camera_config['fps'])
                
                # Проверяем, открыта ли камера
                if cam.isOpened():
                    print(f"✓ Устройство открыто успешно")
                    
                    # Пробуем прочитать кадр
                    ret, frame = cam.read()
                    
                    if ret and frame is not None and frame.size > 0:
                        # Получаем параметры камеры
                        actual_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        actual_fps = cam.get(cv2.CAP_PROP_FPS)
                        
                        resolution_str = f"{actual_width}x{actual_height}"
                        fps_str = f"{actual_fps:.1f}"
                        
                        print(f"\n✅ {name} РАБОТАЕТ!")
                        print(f"   Разрешение: {resolution_str}")
                        print(f"   FPS: {fps_str}")
                        print(f"   Размер кадра: {frame.shape}")
                        
                        logger.log_camera_test(name, True, resolution_str, fps_str)
                        
                        # Возвращаем камеру
                        return {'type': 'v4l2', 'camera': cam}
                    else:
                        print(f"⚠️  Устройство открыто, но кадры не читаются")
                        cam.release()
                else:
                    print(f"❌ Не удалось открыть устройство")
                    
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                logger.log_camera_test(name, False, error=str(e))
    
    # Если ничего не найдено
    print(f"\n❌ НЕ НАЙДЕНА РАБОТАЮЩАЯ КАМЕРА!")
    return None