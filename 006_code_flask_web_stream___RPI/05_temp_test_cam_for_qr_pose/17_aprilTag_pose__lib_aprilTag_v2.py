#!/usr/bin/env python3
"""
Детектирование AprilTag маркеров с использованием библиотеки pyapriltags
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
from collections import deque
import datetime

# ВАЖНО: используем правильный импорт!
from pyapriltags import Detector

# ============================================================================
# СОЗДАНИЕ ПАПКИ ДЛЯ ОТЛАДКИ
# ============================================================================

DEBUG_DIR = f"april_debug_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(DEBUG_DIR, exist_ok=True)
print(f"📁 Отладочная папка: {DEBUG_DIR}/")

# Создаем подпапки
os.makedirs(os.path.join(DEBUG_DIR, 'captures'), exist_ok=True)
os.makedirs(os.path.join(DEBUG_DIR, 'debug'), exist_ok=True)

def save_debug_frame(frame, filename, subfolder='captures'):
    """Сохраняет кадр в отладочную папку"""
    folder = os.path.join(DEBUG_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    cv2.imwrite(filepath, frame)
    return filepath

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

CAMERA_TYPE = 'csi'
CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864
CAMERA_FPS = 30

MARKER_SIZE = 20  # мм
MARKER_FAMILY = 'tag36h11'

# Калибровка
CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

WIN_SIZE_PERSENT = 80
SHOW_AXES = True
SHOW_FPS = True

# ============================================================================
# ЗАГРУЗКА КАЛИБРОВКИ
# ============================================================================

print("\n📷 ЗАГРУЗКА КАЛИБРОВКИ")
print("="*50)

try:
    camera_matrix = np.load(CAMERA_MATRIX_FILE)
    dist_coeffs = np.load(DIST_COEFFS_FILE)
    print(f"✅ Матрица камеры загружена")
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
    """Конвертация RGB -> BGR"""
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

def rotation_vector_to_euler_angles(rvec):
    """Преобразование вектора поворота в углы Эйлера"""
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
    
    if roll_deg > 90: roll_deg -= 180
    elif roll_deg < -90: roll_deg += 180
    if yaw_deg > 180: yaw_deg -= 360
    elif yaw_deg < -180: yaw_deg += 360
    
    return roll_deg, pitch_deg, yaw_deg

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ КАМЕРЫ
# ============================================================================

print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)

if CAMERA_TYPE.lower() == 'usb':
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    picam2 = None
    print(f"✅ USB камера")
else:
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
        controls={"FrameRate": CAMERA_FPS, "AfMode": 2},
        buffer_count=4
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    cap = None
    print(f"✅ CSI камера")

width, height = CAMERA_WIDTH, CAMERA_HEIGHT

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
    focal_length = width * 1.2
    camera_matrix = np.array([
        [focal_length, 0, width/2],
        [0, focal_length, height/2],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros((4, 1))

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА (pyapriltags)
# ============================================================================

print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ APRILTAG")
print("="*50)

# Правильная инициализация для pyapriltags [citation:2][citation:4]
at_detector = Detector(
    families=MARKER_FAMILY,
    nthreads=4,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
    decode_sharpening=0.25,
    debug=0
)

print(f"✅ Детектор AprilTag инициализирован")
print(f"   Семейство: {MARKER_FAMILY}")
print(f"   Размер: {MARKER_SIZE} мм")

marker_size_m = MARKER_SIZE / 1000.0

# ============================================================================
# ТЕСТОВЫЙ ЗАХВАТ
# ============================================================================

print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ")
print("="*50)

for i in range(3):
    if picam2:
        frame = picam2.capture_array()
    else:
        ret, frame = cap.read()
    
    if frame is not None:
        frame = correct_colors(frame)
        print(f"   ✅ Кадр {i+1}: {frame.shape}")
        if i == 0:
            save_debug_frame(frame, 'test_april.jpg')
            print(f"      Сохранен: {DEBUG_DIR}/test_april.jpg")
    time.sleep(0.1)

# ============================================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================================

print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ APRILTAG")
print("="*50)
print("   Управление:")
print("     q - выход")
print("     s - сохранить кадр")
print("     d - режим отладки")
print(f"   Файлы сохраняются в: {DEBUG_DIR}/")
print("-"*50)

fps_timestamps = deque(maxlen=30)
frame_count = 0
debug_mode = False

while True:
    # Захват кадра
    if picam2:
        frame_rgb = picam2.capture_array()
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    else:
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    frame_count += 1
    
    # Измерение FPS
    fps_timestamps.append(time.time())
    if len(fps_timestamps) > 1:
        fps = len(fps_timestamps) / (fps_timestamps[-1] - fps_timestamps[0])
    else:
        fps = 0
    
    # Конвертируем в градации серого для AprilTag
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Детектирование AprilTag с помощью pyapriltags [citation:2]
    detections = at_detector.detect(
        gray,
        estimate_tag_pose=True,
        camera_params=[camera_matrix[0,0], camera_matrix[1,1], 
                      camera_matrix[0,2], camera_matrix[1,2]],
        tag_size=marker_size_m
    )
    
    # Отображение информации
    info_y = 30
    
    if len(detections) > 0:
        cv2.putText(frame, f"✅ Найдено: {len(detections)}", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        print(f"\n📌 Кадр {frame_count}: Найдено {len(detections)} маркеров")
        
        for i, detection in enumerate(detections):
            # Получаем углы маркера
            corners = np.array(detection.corners, dtype=np.float32)
            
            # Рисуем контур
            pts = corners.reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            
            # Рисуем ID
            center = tuple(np.mean(corners, axis=0).astype(int))
            cv2.putText(frame, f"ID:{detection.tag_id}", 
                       (center[0]-20, center[1]-20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # Получаем pose из detection [citation:2]
            if hasattr(detection, 'pose_R') and hasattr(detection, 'pose_t'):
                # Конвертируем rotation matrix в rotation vector
                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                
                if SHOW_AXES:
                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs,
                                     rvec, tvec, marker_size_m/2)
                
                # Вычисляем углы
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                distance = np.linalg.norm(tvec)
                
                # Вывод в консоль
                print(f"   ID:{detection.tag_id}: d={distance:.3f}м, "
                      f"x={tvec[0][0]:.3f}м, y={tvec[1][0]:.3f}м, "
                      f"r={roll:.1f}°, p={pitch:.1f}°, y={yaw:.1f}°")
                
                # Отображение расстояния
                cv2.putText(frame, f"{distance:.2f}m", 
                           (center[0]-20, center[1]+30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "❌ Маркеры не найдены", (10, info_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # Отображение FPS
    if SHOW_FPS:
        cv2.putText(frame, f"FPS: {fps:.1f}", 
                   (frame.shape[1] - 150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Масштабирование и показ
    scale = WIN_SIZE_PERSENT / 100
    display_width = int(frame.shape[1] * scale)
    display_height = int(frame.shape[0] * scale)
    frame_display = cv2.resize(frame, (display_width, display_height))
    
    cv2.imshow('AprilTag Detection', frame_display)
    
    # Обработка клавиш
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('d'):
        debug_mode = not debug_mode
        print(f"🔍 Режим отладки: {'ВКЛ' if debug_mode else 'ВЫКЛ'}")
    elif key == ord('s'):
        filename = f'april_capture_{frame_count}.jpg'
        filepath = save_debug_frame(frame, filename)
        print(f"📸 Сохранено: {filepath}")

# ============================================================================
# ОЧИСТКА
# ============================================================================

print("\n👋 Завершение...")
if picam2:
    picam2.stop()
else:
    cap.release()
cv2.destroyAllWindows()
print("✅ Программа завершена")