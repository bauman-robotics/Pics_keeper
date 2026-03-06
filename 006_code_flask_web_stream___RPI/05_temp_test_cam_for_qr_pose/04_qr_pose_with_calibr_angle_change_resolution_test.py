import cv2
import numpy as np
import re
import subprocess
import time
import os

# ===== НАСТРОЙКИ =====
CAMERA_DEVICE = '/dev/video6'
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864

CAMERA_WIDTH = 2304
CAMERA_HEIGHT = 1296

CAMERA_WIDTH = 4608
CAMERA_HEIGHT = 2592

# imx708
# • 4608x2592 @ 14-15fps
# • 2304x1296 @ 30-56fps
# • 1920x1080 @ 30-50fps
# • 1536x864 @ 90-120fps (HDR)
# • 1280x720 @ 30-100fps
# • 640x480 @ 120fps

CALIB_WIDTH = 640
CALIB_HEIGHT = 480

# Загружаем калибровку
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load('04_cam_imx708_calibration_results/camera_matrix_imx708.npy')
dist_coeffs = np.load('04_cam_imx708_calibration_results/dist_coeffs_imx708.npy')
print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")

def parse_qr_data(data):
    """Извлекает размер из строки формата '25mm_M1'"""
    try:
        match = re.match(r'^([\d.]+)(mm|cm|m)_', data)
        if not match:
            return None
        value, unit = match.groups()
        value = float(value)
        if unit == 'mm':
            return value *2 / 1000.0
        elif unit == 'cm':
            return value / 100.0
        elif unit == 'm':
            return value
    except:
        return None

def get_3d_model_points(marker_size_meters):
    half = marker_size_meters / 2.0
    return np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float32)

def rotation_vector_to_euler_angles(rvec):
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
    singular = sy < 1e-6
    
    if not singular:
        roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2])
        pitch = np.arctan2(-rotation_matrix[2,0], sy)
        yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0])
    else:
        roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1])
        pitch = np.arctan2(-rotation_matrix[2,0], sy)
        yaw = 0
    
    roll_deg = np.degrees(roll)
    pitch_deg = np.degrees(pitch)
    yaw_deg = np.degrees(yaw)
    
    if roll_deg > 90:
        roll_deg = roll_deg - 180
    elif roll_deg < -90:
        roll_deg = roll_deg + 180
    
    if yaw_deg > 180:
        yaw_deg -= 360
    elif yaw_deg < -180:
        yaw_deg += 360
    
    return roll_deg, pitch_deg, yaw_deg

qr_detector = cv2.QRCodeDetector()

# ===== ПРОВЕРКА ДОСТУПНОСТИ КАМЕРЫ =====
print(f"\n🔍 ПРОВЕРКА КАМЕРЫ {CAMERA_DEVICE}")
print("="*50)

# Проверяем через v4l2
result = subprocess.run(['v4l2-ctl', '-d', CAMERA_DEVICE, '--all'], 
                       capture_output=True, text=True)
if result.returncode != 0:
    print(f"❌ Ошибка доступа к {CAMERA_DEVICE}")
    print("   Возможно, камера занята или нет прав")
    print("\n   Проверьте процессы:")
    os.system(f"sudo lsof {CAMERA_DEVICE} 2>/dev/null || echo '   Камера свободна'")
    exit()
else:
    print(f"✅ Камера {CAMERA_DEVICE} доступна через v4l2")

# ===== ИНИЦИАЛИЗАЦИЯ КАМЕРЫ =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)

# Пробуем разные бэкенды
backends = [
    (cv2.CAP_V4L2, "V4L2"),
    (cv2.CAP_ANY, "ANY"),
]

cap = None
for backend, name in backends:
    print(f"   Пробуем бэкенд: {name}")
    cap = cv2.VideoCapture(CAMERA_DEVICE, backend)
    if cap.isOpened():
        print(f"   ✅ Успешно с бэкендом {name}")
        break
    else:
        print(f"   ❌ Не удалось открыть с бэкендом {name}")
        cap.release()
        cap = None

if not cap:
    print("❌ Не удалось открыть камеру ни с одним бэкендом")
    exit()

print(f"\n✅ Камера открыта")
print(f"   Бэкенд: {cap.getBackendName()}")

# Устанавливаем разрешение
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Минимальный буфер

time.sleep(0.5)

# Проверяем разрешение
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"\n🎯 Разрешение: {actual_width}x{actual_height}")

# ===== ТЕСТОВЫЙ ЗАХВАТ =====
print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ (5 кадров)")
print("="*50)

success_count = 0
for i in range(5):
    ret, frame = cap.read()
    if ret and frame is not None:
        success_count += 1
        print(f"   ✅ Кадр {i+1}: успешно, размер={frame.shape}")
        # Сохраняем первый кадр для проверки
        if i == 0:
            cv2.imwrite('test_frame.jpg', frame)
            print(f"      Первый кадр сохранен как test_frame.jpg")
    else:
        print(f"   ❌ Кадр {i+1}: не получен")
    time.sleep(0.1)

if success_count == 0:
    print("\n❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ НИ ОДНОГО КАДРА!")
    print("\n   Возможные причины:")
    print("   1. Камера уже используется другим процессом")
    print("   2. Нет прав доступа к устройству")
    print("   3. Проблема с драйвером камеры")
    print("\n   Проверьте:")
    print("   sudo lsof /dev/video6")
    print("   ls -la /dev/video6")
    print("   v4l2-ctl -d /dev/video6 --all")
    cap.release()
    exit()

# ===== ОСНОВНОЙ ЦИКЛ =====
print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {actual_width}x{actual_height}")
print(f"   Используются откалиброванные параметры камеры!\n")

frame_count = 0
error_count = 0

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        error_count += 1
        if error_count > 10:
            print("\n⚠️  Слишком много ошибок захвата, останавливаюсь")
            break
        print(f"⚠️  Ошибка захвата кадра #{error_count}")
        time.sleep(0.1)
        continue
    
    frame_count += 1
    error_count = 0
    
    # Детектируем QR-код
    data, points, _ = qr_detector.detectAndDecode(frame)
    
    if data and points is not None:
        marker_size = parse_qr_data(data)
        
        if marker_size:
            points = points.reshape(-1, 2).astype(np.float32)
            
            # Рисуем контур
            for i in range(4):
                pt1 = tuple(points[i].astype(int))
                pt2 = tuple(points[(i+1)%4].astype(int))
                cv2.line(frame, pt1, pt2, (0, 255, 0), 3)
            
            # Решаем PnP
            object_points = get_3d_model_points(marker_size)
            
            success, rvec, tvec = cv2.solvePnP(
                object_points,
                points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            
            if success:
                # Получаем углы
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                distance = np.linalg.norm(tvec)
                
                print(f"\n📌 Распознан код: {data}")
                print(f"   Расстояние: {distance:.3f} м")
                print(f"   Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
                
                # Рисуем оси
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_size/2)
    
    # Показываем кадр
    cv2.imshow('QR Pose Estimation', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\n👋 Программа завершена")