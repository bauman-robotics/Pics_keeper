import cv2
import numpy as np
import re
from picamera2 import Picamera2
import time

# ===== НАСТРОЙКИ =====
CAMERA_ID = 0  # 0 - IMX708, 1 - IMX415
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


# ===== НАСТРОЙКИ =====
CAMERA_DEVICE = '/dev/video6'
#CAMERA_WIDTH = 640
#CAMERA_HEIGHT = 480

#CAMERA_WIDTH = 1280
#CAMERA_HEIGHT = 720

CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864

#CAMERA_WIDTH = 2304
#CAMERA_HEIGHT = 1296

#CAMERA_WIDTH = 4608
#CAMERA_HEIGHT = 2592

# imx708
# • 4608x2592 @ 14-15fps
# • 2304x1296 @ 30-56fps
# • 1920x1080 @ 30-50fps
# • 1536x864 @ 90-120fps (HDR)
# • 1280x720 @ 30-100fps
# • 640x480 @ 120fps

CALIB_WIDTH = 640
CALIB_HEIGHT = 480

CAMERA_FPS = 30


# Загружаем результаты калибровки
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
            return value / 1000.0  # Убрал умножение на 2, так как в QR коде уже размер стороны
        elif unit == 'cm':
            return value / 100.0
        elif unit == 'm':
            return value
    except:
        return None

def get_3d_model_points(marker_size_meters):
    """Создает 3D-точки углов QR-кода"""
    half = marker_size_meters / 2.0
    return np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float32)

def rotation_vector_to_euler_angles(rvec):
    """Преобразует вектор Родрига в углы Эйлера"""
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
    
    # Нормализация углов
    if roll_deg > 90:
        roll_deg = roll_deg - 180
    elif roll_deg < -90:
        roll_deg = roll_deg + 180
    
    if yaw_deg > 180:
        yaw_deg -= 360
    elif yaw_deg < -180:
        yaw_deg += 360
    
    return roll_deg, pitch_deg, yaw_deg

# ===== ИНИЦИАЛИЗАЦИЯ PICAMERA2 =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ PICAMERA2 (камера #{CAMERA_ID})")
print("="*50)

try:
    picam2 = Picamera2(CAMERA_ID)
    
    # Создаем конфигурацию
    config = picam2.create_video_configuration(
        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "BGR888"},
        controls={"FrameRate": CAMERA_FPS},
        buffer_count=4
    )
    
    picam2.configure(config)
    picam2.start()
    
    # Даем камере время на инициализацию
    time.sleep(1)
    
    print(f"✅ Picamera2 инициализирована")
    print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
    print(f"   FPS: {CAMERA_FPS}")
    
except Exception as e:
    print(f"❌ Ошибка инициализации Picamera2: {e}")
    exit()

# ===== ТЕСТОВЫЙ ЗАХВАТ =====
print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ (5 кадров)")
print("="*50)

for i in range(5):
    frame = picam2.capture_array()
    if frame is not None:
        print(f"   ✅ Кадр {i+1}: успешно, размер={frame.shape}")
        if i == 0:
            cv2.imwrite('test_frame_picamera2.jpg', frame)
            print(f"      Первый кадр сохранен как test_frame_picamera2.jpg")
    else:
        print(f"   ❌ Кадр {i+1}: не получен")
    time.sleep(0.1)

# ===== ОСНОВНОЙ ЦИКЛ =====
print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
print(f"   Используются откалиброванные параметры камеры!\n")

qr_detector = cv2.QRCodeDetector()
frame_count = 0

while True:
    # Захват кадра через Picamera2
    frame = picam2.capture_array()
    
    if frame is None:
        print("⚠️  Ошибка захвата кадра")
        time.sleep(0.1)
        continue
    
    frame_count += 1
    
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
            
            # Создаем 3D-модель и решаем PnP
            object_points = get_3d_model_points(marker_size)
            
            success, rvec, tvec = cv2.solvePnP(
                object_points,
                points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            
            if success:
                # Получаем углы поворота
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                distance = np.linalg.norm(tvec)
                
                print(f"\n📌 Распознан код: {data}")
                print(f"   Расстояние: {distance:.3f} м")
                print(f"   Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
                
                # Рисуем оси координат
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_size/2)
                
                # Выводим информацию на кадр
                cv2.putText(frame, f"Dist: {distance:.2f}m", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Roll: {roll:.1f}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, f"Pitch: {pitch:.1f}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, f"Yaw: {yaw:.1f}", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    # Показываем кадр
    cv2.imshow('QR Pose Estimation (Picamera2)', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Очистка
picam2.stop()
cv2.destroyAllWindows()
print("\n👋 Программа завершена")