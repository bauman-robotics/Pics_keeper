#!/usr/bin/env python3
"""
Детектирование и оценка позы AprilTag маркеров (tag36h11)
Оптимизированная версия с улучшенным детектированием
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
from collections import deque

# ============================================================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ============================================================================

CAMERA_TYPE = 'csi'
USB_CAMERA_ID = 0
CSI_CAMERA_ID = 0

# УМЕНЬШИМ РАЗРЕШЕНИЕ для лучшего детектирования
CAMERA_WIDTH = 640  # Было 1536
CAMERA_HEIGHT = 480  # Было 864
CAMERA_FPS = 30

MARKER_SIZE = 20  # мм
MARKER_FAMILY = 'tag36h11'

CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

WIN_SIZE_PERSENT = 100
SHOW_AXES = True
SHOW_FPS = True

# ============================================================================
# ЗАГРУЗКА КАЛИБРОВКИ
# ============================================================================

print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)

try:
    camera_matrix = np.load(CAMERA_MATRIX_FILE)
    dist_coeffs = np.load(DIST_COEFFS_FILE)
    print(f"✅ Матрица камеры загружена:")
    print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
    CALIB_LOADED = True
except Exception as e:
    print(f"⚠️ Калибровка не загружена: {e}")
    camera_matrix = None
    dist_coeffs = None
    CALIB_LOADED = False

# ============================================================================
# ФУНКЦИИ
# ============================================================================

def correct_colors(frame):
    """Принудительная конвертация RGB -> BGR"""
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

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
    
    return np.degrees(roll), np.degrees(pitch), np.degrees(yaw)

def enhance_contrast(frame):
    """Улучшение контраста для лучшего детектирования"""
    # Конвертируем в градации серого
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Применяем адаптивную нормализацию
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    # Обратно в BGR
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ КАМЕРЫ
# ============================================================================

print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)
print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")

if CAMERA_TYPE.lower() == 'usb':
    cap = cv2.VideoCapture(USB_CAMERA_ID)
    if not cap.isOpened():
        print(f"❌ Ошибка: не удалось открыть USB камеру")
        exit()
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    width, height = CAMERA_WIDTH, CAMERA_HEIGHT
    picam2 = None
    print(f"✅ USB камера открыта")
else:
    try:
        picam2 = Picamera2(CSI_CAMERA_ID)
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            controls={
                "FrameRate": CAMERA_FPS,
                "AfMode": 2,
                "AfSpeed": 1,
                "Brightness": 0.5,  # Добавим настройки
                "Contrast": 1.0,
                "Sharpness": 1.0
            },
            buffer_count=4
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        width, height = CAMERA_WIDTH, CAMERA_HEIGHT
        cap = None
        print(f"✅ CSI камера инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации CSI камеры: {e}")
        exit()

# ============================================================================
# МАСШТАБИРОВАНИЕ КАЛИБРОВКИ
# ============================================================================

if CALIB_LOADED and camera_matrix is not None:
    if width != CALIB_WIDTH or height != CALIB_HEIGHT:
        scale_x = width / CALIB_WIDTH
        scale_y = height / CALIB_HEIGHT
        scale = (scale_x + scale_y) / 2
        
        camera_matrix_scaled = camera_matrix.copy()
        camera_matrix_scaled[0,0] *= scale
        camera_matrix_scaled[1,1] *= scale
        camera_matrix_scaled[0,2] *= scale_x
        camera_matrix_scaled[1,2] *= scale_y
        
        print(f"\n🔄 Масштабирование: {scale:.3f}")
        camera_matrix = camera_matrix_scaled
else:
    # Создаем приблизительную матрицу
    focal_length = width * 1.2
    camera_matrix = np.array([
        [focal_length, 0, width/2],
        [0, focal_length, height/2],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros((4, 1))

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ДЕТЕКТОРА С ОПТИМИЗИРОВАННЫМИ ПАРАМЕТРАМИ
# ============================================================================

print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ ДЕТЕКТОРА")
print("="*50)

# Используем стандартный словарь ArUco
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# НАСТРАИВАЕМ ПАРАМЕТРЫ ДЕТЕКТОРА
parameters = cv2.aruco.DetectorParameters()

# Параметры адаптивного порога (критично для распознавания)
parameters.adaptiveThreshWinSizeMin = 3      # Минимальный размер окна
parameters.adaptiveThreshWinSizeMax = 23     # Максимальный размер окна
parameters.adaptiveThreshWinSizeStep = 10    # Шаг изменения
parameters.adaptiveThreshConstant = 7        # Константа порога (увеличили)

# Параметры контура
parameters.minMarkerPerimeterRate = 0.03     # Минимальный периметр (уменьшили)
parameters.maxMarkerPerimeterRate = 4.0      # Максимальный периметр
parameters.polygonalApproxAccuracyRate = 0.03 # Точность аппроксимации

# Параметры битовой матрицы
parameters.minCornerDistanceRate = 0.05      # Минимальное расстояние между углами
parameters.minDistanceToBorder = 3           # Минимальное расстояние до границы
parameters.minMarkerDistanceRate = 0.05      # Минимальное расстояние между маркерами

# Параметры углов
parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX  # Уточнение углов
parameters.cornerRefinementWinSize = 5
parameters.cornerRefinementMaxIterations = 30
parameters.cornerRefinementMinAccuracy = 0.1

# Параметры перспективного искажения
parameters.perspectiveRemovePixelPerCell = 4  # Пикселей на ячейку
parameters.perspectiveRemoveIgnoredMarginPerCell = 0.13  # Игнорируемый край

print(f"   Словарь: DICT_6X6_250")
print(f"   Размер маркера: {MARKER_SIZE} мм")
print(f"   Параметры: адаптивный порог={parameters.adaptiveThreshConstant}")
print(f"             мин.периметр={parameters.minMarkerPerimeterRate}")

detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
marker_size_m = MARKER_SIZE / 1000.0

# ============================================================================
# ТЕСТОВЫЙ ЗАХВАТ
# ============================================================================

print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ")
print("="*50)

for i in range(3):
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if ret and frame is not None:
            frame = correct_colors(frame)
            print(f"   ✅ Кадр {i+1}: {frame.shape}")
    else:
        frame = picam2.capture_array()
        if frame is not None:
            frame = correct_colors(frame)
            print(f"   ✅ Кадр {i+1}: {frame.shape}")
    time.sleep(0.1)

# ============================================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================================

print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print("   Нажмите 'e' для улучшения контраста")
print(f"   Разрешение: {width}x{height}")
print("-"*50)

fps_timestamps = deque(maxlen=30)
frame_count = 0
use_enhance = False  # Флаг для улучшения контраста

while True:
    # Захват кадра
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        frame = correct_colors(frame)
    else:
        frame = picam2.capture_array()
        if frame is None:
            continue
        frame = correct_colors(frame)
    
    frame_count += 1
    
    # Опциональное улучшение контраста
    if use_enhance:
        display_frame = enhance_contrast(frame)
    else:
        display_frame = frame.copy()
    
    # Измерение FPS
    fps_timestamps.append(time.time())
    if len(fps_timestamps) > 1:
        fps = len(fps_timestamps) / (fps_timestamps[-1] - fps_timestamps[0])
    else:
        fps = 0
    
    # Детектирование
    corners, ids, rejected = detector.detectMarkers(display_frame)
    
    # Отображение статуса
    status_y = 30
    if ids is not None and len(ids) > 0:
        cv2.putText(display_frame, f"✅ Найдено: {len(ids)}", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        print(f"\n✅ Кадр {frame_count}: Найдено маркеров: {len(ids)}")
        
        # Рисуем маркеры
        cv2.aruco.drawDetectedMarkers(display_frame, corners, ids)
        
        # Оценка позы
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, marker_size_m, camera_matrix, dist_coeffs
        )
        
        for i in range(len(ids)):
            if SHOW_AXES:
                cv2.drawFrameAxes(display_frame, camera_matrix, dist_coeffs,
                                 rvecs[i], tvecs[i], marker_size_m/2)
            
            # Вывод информации
            roll, pitch, yaw = rotation_vector_to_euler_angles(rvecs[i])
            x, y, distance = tvecs[i][0]
            
            print(f"   ID:{ids[i][0]}: d={distance:.3f}м, x={x:.3f}м, y={y:.3f}м")
    else:
        # Показываем количество отвергнутых кандидатов
        rejected_count = len(rejected) if rejected is not None else 0
        color = (0, 0, 255) if rejected_count > 0 else (128, 128, 128)
        cv2.putText(display_frame, f"❌ Отброшено: {rejected_count}", (10, status_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Рисуем отвергнутые кандидаты для отладки
        if rejected_count > 0 and frame_count % 10 == 0:
            for reject in rejected:
                pts = reject.reshape(-1, 2).astype(int)
                cv2.polylines(display_frame, [pts], True, (0, 0, 255), 1)
    
    # Отображение FPS
    if SHOW_FPS:
        cv2.putText(display_frame, f"FPS: {fps:.1f}", 
                   (display_frame.shape[1] - 150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Информация о режиме
    if use_enhance:
        cv2.putText(display_frame, "ENHANCED", 
                   (display_frame.shape[1] - 150, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    # Масштабирование и показ
    scale = WIN_SIZE_PERSENT / 100
    display_width = int(display_frame.shape[1] * scale)
    display_height = int(display_frame.shape[0] * scale)
    frame_display = cv2.resize(display_frame, (display_width, display_height))
    
    cv2.imshow('AprilTag Detection', frame_display)
    
    # Обработка клавиш
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('e'):
        use_enhance = not use_enhance
        print(f"🔆 Улучшение контраста: {'ВКЛ' if use_enhance else 'ВЫКЛ'}")
    elif key == ord('s'):
        cv2.imwrite(f'capture_{frame_count}.jpg', display_frame)
        print(f"📸 Кадр сохранен: capture_{frame_count}.jpg")

# ============================================================================
# ОЧИСТКА
# ============================================================================

print("\n👋 Завершение...")
if CAMERA_TYPE.lower() == 'usb':
    cap.release()
else:
    picam2.stop()
cv2.destroyAllWindows()
print("✅ Программа завершена")