import cv2
import numpy as np
import re
from collections import deque

# ===== НАСТРОЙКИ =====
# Выбор камеры (0 - первая, 1 - вторая, 2 - третья и т.д.)
CAMERA_ID = 6  # измените при необходимости

# Желаемое разрешение
CAMERA_WIDTH = 640 # 1280 # 1920   # или 1280, 2592 и т.д.
CAMERA_HEIGHT = 480 # 720 # 1080  # или 720, 1944 и т.д.

# Параметры калибровки (разрешение, для которого делалась калибровка)
CALIB_WIDTH = 640
CALIB_HEIGHT = 480

# Загружаем результаты калибровки
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load('04_cam_imx708_calibration_results/camera_matrix_imx708.npy')
dist_coeffs = np.load('04_cam_imx708_calibration_results/dist_coeffs_imx708.npy')
print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")
print(f"✅ Коэффициенты дисторсии: {dist_coeffs.reshape(-1)}")

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
    """Создает 3D-точки углов QR-кода"""
    half = marker_size_meters / 2.0
    return np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float32)

def rotation_vector_to_euler_angles(rvec):
    """
    Преобразует вектор Родрига в углы Эйлера (roll, pitch, yaw) в градусах
    """
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

def get_plane_normal_from_rvec(rvec):
    """Получает вектор нормали плоскости маркера"""
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    normal_local = np.array([0, 0, 1]).reshape(3,1)
    normal_global = rotation_matrix @ normal_local
    return normal_global.flatten()

# Инициализация детектора
qr_detector = cv2.QRCodeDetector()

# ===== ИНИЦИАЛИЗАЦИЯ КАМЕРЫ =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ #{CAMERA_ID}")
print("="*50)
cap = cv2.VideoCapture(CAMERA_ID)
if not cap.isOpened():
    print(f"❌ Ошибка: не удалось открыть камеру #{CAMERA_ID}")
    print("   Доступные камеры:")
    for i in range(5):  # Проверяем первые 5 индексов
        test_cap = cv2.VideoCapture(i)
        if test_cap.isOpened():
            print(f"   ✅ Камера #{i} доступна")
            test_cap.release()
        else:
            print(f"   ❌ Камера #{i} недоступна")
    exit()

# Получаем информацию о камере
backend = cap.getBackendName()
print(f"✅ Камера #{CAMERA_ID} открыта")
print(f"   Бэкенд: {backend}")

# Получаем поддерживаемые разрешения (опционально)
print("\n📊 ПОДДЕРЖИВАЕМЫЕ РАЗРЕШЕНИЯ:")
common_resolutions = [(640,480), (800,600), (1024,768), (1280,720), (1920,1080), (2592,1944)]
for w, h in common_resolutions:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    test_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    test_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if test_w == w and test_h == h:
        print(f"   ✅ {w}x{h} - поддерживается")
    else:
        print(f"   ❌ {w}x{h} - не поддерживается (макс. {test_w}x{test_h})")

# Устанавливаем желаемое разрешение
print(f"\n🎯 УСТАНОВКА РАЗРЕШЕНИЯ")
print("="*50)
print(f"   Запрошено: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

# Проверяем, какое разрешение реально установилось
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)

print(f"✅ Реальное разрешение: {actual_width}x{actual_height}")
print(f"✅ FPS: {actual_fps:.1f}")

# Используем actual_width/actual_height для дальнейшей работы
width, height = actual_width, actual_height

# ===== МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ КАЛИБРОВКИ =====
print(f"\n🔄 МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ")
print("="*50)
print(f"   Калибровка: {CALIB_WIDTH}x{CALIB_HEIGHT}")
print(f"   Текущее: {width}x{height}")

if width != CALIB_WIDTH or height != CALIB_HEIGHT:
    scale_x = width / CALIB_WIDTH
    scale_y = height / CALIB_HEIGHT
    
    camera_matrix_scaled = camera_matrix.copy()
    camera_matrix_scaled[0,0] *= scale_x  # fx
    camera_matrix_scaled[1,1] *= scale_y  # fy
    camera_matrix_scaled[0,2] *= scale_x  # cx
    camera_matrix_scaled[1,2] *= scale_y  # cy
    
    print(f"✅ Параметры отмасштабированы:")
    print(f"   Коэффициенты: x={scale_x:.2f}, y={scale_y:.2f}")
    print(f"   fx = {camera_matrix_scaled[0,0]:.1f} (было {camera_matrix[0,0]:.1f})")
    print(f"   fy = {camera_matrix_scaled[1,1]:.1f} (было {camera_matrix[1,1]:.1f})")
    print(f"   cx = {camera_matrix_scaled[0,2]:.1f} (было {camera_matrix[0,2]:.1f})")
    print(f"   cy = {camera_matrix_scaled[1,2]:.1f} (было {camera_matrix[1,2]:.1f})")
    
    camera_matrix = camera_matrix_scaled
else:
    print(f"✅ Разрешение совпадает, масштабирование не требуется")

print("\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print("   Используются откалиброванные параметры камеры!\n")

while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️  Ошибка захвата кадра")
        break
    
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
                # Получаем углы поворота в градусах
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                
                # Получаем вектор нормали плоскости
                normal = get_plane_normal_from_rvec(rvec)
                
                # Выводим в консоль с углами
                distance = np.linalg.norm(tvec)
                print(f"\n📌 Распознан код: {data}")
                print(f"  📍 Позиция: x={tvec[0][0]:.3f}, y={tvec[1][0]:.3f}, z={tvec[2][0]:.3f} м")
                print(f"  📏 Расстояние: {distance:.3f} м")
                print(f"  🔄 Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
                print(f"  ⬆️ Нормаль: [{normal[0]:.2f}, {normal[1]:.2f}, {normal[2]:.2f}]")
                
                # Рисуем оси координат
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_size/2)
                
                # Выводим информацию на кадр
                cv2.putText(frame, f"ID: {data}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"X: {tvec[0][0]:.3f} m", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Y: {tvec[1][0]:.3f} m", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Z: {tvec[2][0]:.3f} m", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Добавляем углы на кадр
                cv2.putText(frame, f"Roll: {roll:.1f}", (10, 180),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, f"Pitch: {pitch:.1f}", (10, 210),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.putText(frame, f"Yaw: {yaw:.1f}", (10, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    cv2.imshow('QR Pose Estimation', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\n👋 Программа завершена")