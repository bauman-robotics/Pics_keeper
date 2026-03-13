import cv2
import time
import os

# ВАЖНО: Заставляем OpenCV использовать V4L2
os.environ["OPENCV_VIDEOIO_PRIORITY_LIST"] = "V4L2"

def setup_global_shutter_camera(camera_id=0):
    """Настройка USB-камеры с глобальным затвором"""
    
    # Явно указываем V4L2 backend
    cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
    
    # Проверяем, открылась ли камера
    if not cap.isOpened():
        print("❌ Не удалось открыть камеру через V4L2")
        # Попробуем альтернативный метод
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            return None
    
    # Даем камере время на инициализацию
    time.sleep(0.5)
    
    # Устанавливаем формат MJPG (предпочтительный для вашей камеры)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
    
    # Настройки для максимальной производительности
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1200)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)    
    cap.set(cv2.CAP_PROP_FPS, 60)
    
    # Для глобального затвора важна выдержка
    # Отключаем автоэкспозицию
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 0.25 = off
    
    # Получаем реальные настройки
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = chr(actual_fourcc & 0xFF) + chr((actual_fourcc >> 8) & 0xFF) + chr((actual_fourcc >> 16) & 0xFF) + chr((actual_fourcc >> 24) & 0xFF)
    
    print(f"✅ Камера настроена: {actual_width}x{actual_height} @ {actual_fps} fps, кодек: {fourcc_str}")
    
    # Проверяем, что камера действительно отдает кадры
    ret, frame = cap.read()
    if ret:
        print(f"✅ Тестовый кадр получен, размер: {frame.shape}")
    else:
        print("❌ Не удалось получить тестовый кадр")
    
    return cap

# Использование
print("🔄 Открываю камеру...")
cap = setup_global_shutter_camera(8)

if cap:
    print("📸 Делаю снимки...")
    for i in range(5):
        ret, frame = cap.read()
        if ret:
            filename = f'test_global_{i}.jpg'
            cv2.imwrite(filename, frame)
            print(f"   ✅ Снимок {i} сохранен: {filename}")
        else:
            print(f"   ❌ Не удалось получить кадр {i}")
        time.sleep(0.1)
    
    cap.release()
    print("✅ Камера закрыта")
else:
    print("❌ Не удалось открыть камеру")