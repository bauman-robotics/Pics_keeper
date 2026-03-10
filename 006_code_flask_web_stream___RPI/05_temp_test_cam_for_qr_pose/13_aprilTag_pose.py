#!/usr/bin/env python3
"""
Детектирование и оценка позы AprilTag маркеров (tag36h11)
Поддерживает USB и CSI камеры (Raspberry Pi Camera Module)
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
import re
from collections import deque

# ============================================================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ (В ШАПКЕ, КАК В ИСХОДНОМ СКРИПТЕ)
# ============================================================================

# ===== НАСТРОЙКИ КАМЕРЫ =====
CAMERA_TYPE = 'csi'  # 'usb' или 'csi'
USB_CAMERA_ID = 0
CSI_CAMERA_ID = 0

# ===== НАСТРОЙКИ РАЗРЕШЕНИЯ =====
CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864
CAMERA_FPS = 30

# ===== НАСТРОЙКИ МАРКЕРА =====
MARKER_SIZE = 20  # размер в мм (20 мм для вашего маркера)
MARKER_FAMILY = 'tag36h11'  # семейство AprilTag

# ===== НАСТРОЙКИ КАЛИБРОВКИ =====
CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

# ===== НАСТРОЙКИ ОТОБРАЖЕНИЯ =====
WIN_SIZE_PERSENT = 80  # размер окна в процентах
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
    print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
    print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
    print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")
    CALIB_LOADED = True
except Exception as e:
    print(f"⚠️ Калибровка не загружена: {e}")
    print("   Будет использована приблизительная матрица")
    camera_matrix = None
    dist_coeffs = None
    CALIB_LOADED = False

# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С AprilTag
# ============================================================================

def get_aruco_dict(family='tag36h11'):
    """Возвращает словарь ArUco для указанного семейства AprilTag"""
    
    # Словарь доступных семейств в OpenCV
    family_map = {
        'tag16h5': cv2.aruco.DICT_6X6_250,  # Замена для AprilTag 16h5
        'tag25h9': cv2.aruco.DICT_5X5_250,  # Замена для AprilTag 25h9
        'tag36h11': cv2.aruco.DICT_6X6_250,  # Замена для AprilTag 36h11
        'tagCircle21h7': cv2.aruco.DICT_7X7_250,  # Замена
        'tagCircle49h12': cv2.aruco.DICT_7X7_1000,  # Замена
        'tagStandard41h12': cv2.aruco.DICT_ARUCO_ORIGINAL,  # Замена
        'tagStandard52h13': cv2.aruco.DICT_ARUCO_ORIGINAL,  # Замена
    }
    
    # По умолчанию используем DICT_6X6_250
    default_dict = cv2.aruco.DICT_6X6_250
    
    if family in family_map:
        dict_id = family_map[family]
        print(f"✅ Используется словарь: {family} -> ID {dict_id}")
    else:
        dict_id = default_dict
        print(f"⚠️ Семейство '{family}' не найдено, использую DICT_6X6_250")
    
    return cv2.aruco.getPredefinedDictionary(dict_id)

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

def correct_colors(frame, camera_type):
    """Корректирует порядок цветов в зависимости от типа камеры"""
    if camera_type == 'usb':
        # USB камеры часто отдают RGB, конвертируем в BGR
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:
        # CSI камеры через Picamera2 отдают RGB, нужно конвертировать в BGR!
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ КАМЕРЫ
# ============================================================================

print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")

if CAMERA_TYPE.lower() == 'usb':
    # ===== USB КАМЕРА =====
    cap = cv2.VideoCapture(USB_CAMERA_ID)
    if not cap.isOpened():
        print(f"❌ Ошибка: не удалось открыть USB камеру #{USB_CAMERA_ID}")
        exit()
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"✅ USB камера открыта")
    print(f"   Разрешение: {actual_width}x{actual_height}")
    
    width, height = actual_width, actual_height
    picam2 = None

else:  # CSI
    # ===== CSI КАМЕРА =====
    try:
        picam2 = Picamera2(CSI_CAMERA_ID)
        
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "BGR888"},
            controls={
                "FrameRate": CAMERA_FPS,
                "AfMode": 2,  # непрерывный автофокус
                "AfSpeed": 1
            },
            buffer_count=4
        )
        
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        
        print(f"✅ CSI камера инициализирована")
        print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
        
        width, height = CAMERA_WIDTH, CAMERA_HEIGHT
        cap = None
        
    except Exception as e:
        print(f"❌ Ошибка инициализации CSI камеры: {e}")
        exit()

# ============================================================================
# МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ КАЛИБРОВКИ
# ============================================================================

if CALIB_LOADED and camera_matrix is not None:
    print(f"\n🔄 МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ")
    print("="*50)
    print(f"   Калибровка: {CALIB_WIDTH}x{CALIB_HEIGHT}")
    print(f"   Текущее: {width}x{height}")
    
    if width != CALIB_WIDTH or height != CALIB_HEIGHT:
        scale = width / CALIB_WIDTH
        
        camera_matrix_scaled = camera_matrix.copy()
        camera_matrix_scaled[0,0] *= scale
        camera_matrix_scaled[1,1] *= scale
        camera_matrix_scaled[0,2] *= scale
        camera_matrix_scaled[1,2] *= scale
        
        print(f"✅ Параметры отмасштабированы с коэффициентом {scale:.3f}")
        print(f"   fx = {camera_matrix_scaled[0,0]:.1f}, fy = {camera_matrix_scaled[1,1]:.1f}")
        
        camera_matrix = camera_matrix_scaled
else:
    # Создаем приблизительную матрицу камеры
    print(f"\n🔄 СОЗДАНИЕ ПРИБЛИЗИТЕЛЬНОЙ МАТРИЦЫ")
    print("="*50)
    focal_length = width * 1.2  # приблизительное фокусное расстояние
    camera_matrix = np.array([
        [focal_length, 0, width/2],
        [0, focal_length, height/2],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros((4, 1))
    print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
    print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ДЕТЕКТОРА APRILTAG
# ============================================================================

print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ ДЕТЕКТОРА APRILTAG")
print("="*50)
print(f"   Семейство: {MARKER_FAMILY}")
print(f"   Размер маркера: {MARKER_SIZE} мм ({MARKER_SIZE/1000:.3f} м)")

# Получаем словарь ArUco
aruco_dict = get_aruco_dict(MARKER_FAMILY)
parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

marker_size_m = MARKER_SIZE / 1000.0  # перевод в метры

# ============================================================================
# ТЕСТОВЫЙ ЗАХВАТ
# ============================================================================

print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ (3 кадра)")
print("="*50)

for i in range(3):
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if ret and frame is not None:
            frame = correct_colors(frame, CAMERA_TYPE)
            print(f"   ✅ Кадр {i+1}: успешно, размер={frame.shape}")
            if i == 0:
                cv2.imwrite('test_frame_usb.jpg', frame)
                print(f"      Сохранен как test_frame_usb.jpg")
    else:
        frame = picam2.capture_array()
        if frame is not None:
            frame = correct_colors(frame, CAMERA_TYPE)
            print(f"   ✅ Кадр {i+1}: успешно, размер={frame.shape}")
            if i == 0:
                cv2.imwrite('test_frame_csi.jpg', frame)
                print(f"      Сохранен как test_frame_csi.jpg")
    time.sleep(0.1)

# ============================================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================================

print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ APRILTAG")
print("="*50)
print("   Нажмите 'q' для выхода")
print("   Нажмите 'a' для вкл/выкл осей")
print(f"   Разрешение: {width}x{height}")
print(f"   Размер маркера: {MARKER_SIZE} мм")
print("-"*50)

# Для измерения FPS
fps_timestamps = deque(maxlen=30)
frame_count = 0

while True:
    # Захват кадра
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        frame = correct_colors(frame, CAMERA_TYPE)
    else:
        frame = picam2.capture_array()
        if frame is None:
            continue
        frame = correct_colors(frame, CAMERA_TYPE)
    
    frame_count += 1

    #==========================================================================
    # ========== ДИАГНОСТИКА ==========
    if frame_count % 30 == 0:  # Каждые 30 кадров
        # 1. Проверка цветов
        b_mean = np.mean(frame[:,:,0])
        g_mean = np.mean(frame[:,:,1])
        r_mean = np.mean(frame[:,:,2])
        print(f"\n📊 Диагностика кадра {frame_count}:")
        print(f"   Цвета (BGR): B={b_mean:.1f}, G={g_mean:.1f}, R={r_mean:.1f}")
        print(f"   Формат кадра: {frame.dtype}, {frame.shape}")
        
        # 2. Сохраняем тестовый кадр для проверки
        if frame_count % 300 == 0:
            cv2.imwrite(f'diagnostic_frame_{frame_count}.jpg', frame)
            print(f"   📸 Сохранен diagnostic_frame_{frame_count}.jpg")
    
    # Детектирование AprilTag
    corners, ids, rejected = detector.detectMarkers(frame)
    
    # ========== ОТЛАДКА ДЕТЕКТИРОВАНИЯ ==========
    if ids is not None and len(ids) > 0:
        print(f"\n✅ УСПЕХ! Найдено маркеров: {len(ids)}")
        print(f"   ID: {ids.flatten()}")
    else:
        # Если маркеры не найдены, показываем rejected кандидаты
        if len(rejected) > 0:
            print(f"⚠️ Отброшенных кандидатов: {len(rejected)}")
            # Рисуем отвергнутые кандидаты для отладки
            frame_with_rejected = frame.copy()
            for reject in rejected:
                pts = reject.reshape(-1, 2).astype(int)
                cv2.polylines(frame_with_rejected, [pts], True, (0, 0, 255), 2)
            cv2.imwrite(f'rejected_candidates_{frame_count}.jpg', frame_with_rejected)    
    #==========================================================================
    # Измерение FPS
    fps_timestamps.append(time.time())
    if len(fps_timestamps) > 1:
        fps = len(fps_timestamps) / (fps_timestamps[-1] - fps_timestamps[0])
    else:
        fps = 0
    
    # Детектирование AprilTag маркеров
    corners, ids, rejected = detector.detectMarkers(frame)
    
    if ids is not None and len(ids) > 0:
        # Рисуем контуры маркеров
        cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        
        # Оценка позы для каждого маркера
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, marker_size_m, camera_matrix, dist_coeffs
        )
        
        # Вывод информации в консоль и на экран
        y_offset = 30
        cv2.putText(frame, f"AprilTags found: {len(ids)}", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_offset += 35
        
        for i in range(len(ids)):
            # Рисуем оси координат
            if SHOW_AXES:
                cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, 
                                 rvecs[i], tvecs[i], marker_size_m/2)
            
            # Вычисляем углы Эйлера
            roll, pitch, yaw = rotation_vector_to_euler_angles(rvecs[i])
            
            # Извлекаем смещения
            x = tvecs[i][0][0]
            y = tvecs[i][0][1]
            distance = tvecs[i][0][2]
            
            # Цвет для каждого маркера
            color = (0, 255, 0) if i == 0 else (255, 0, 0) if i == 1 else (0, 0, 255)
            
            # Текст с информацией
            cv2.putText(frame, f"ID:{ids[i][0]}  Dist:{distance:.2f}m", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_offset += 25
            
            cv2.putText(frame, f"  X:{x:.2f}m Y:{y:.2f}m", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_offset += 25
            
            cv2.putText(frame, f"  R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_offset += 35
            
            # Вывод в консоль (каждый 30-й кадр, чтобы не засорять)
            if frame_count % 30 == 0:
                print(f"📌 ID:{ids[i][0]}: d={distance:.3f}м, x={x:.3f}м, y={y:.3f}м, "
                      f"r={roll:.1f}°, p={pitch:.1f}°, y={yaw:.1f}°")
    
    # Отображение FPS
    if SHOW_FPS:
        cv2.putText(frame, f"FPS: {fps:.1f}", (frame.shape[1] - 150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Масштабирование и показ кадра
    scale = WIN_SIZE_PERSENT / 100
    display_width = int(frame.shape[1] * scale)
    display_height = int(frame.shape[0] * scale)
    frame_display = cv2.resize(frame, (display_width, display_height))
    
    cv2.imshow('AprilTag Detection', frame_display)
    
    # Обработка клавиш
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('a'):
        SHOW_AXES = not SHOW_AXES
        print(f"📐 Отображение осей: {'ВКЛ' if SHOW_AXES else 'ВЫКЛ'}")

# ============================================================================
# ОЧИСТКА
# ============================================================================

print("\n👋 Завершение работы...")
if CAMERA_TYPE.lower() == 'usb':
    cap.release()
else:
    picam2.stop()
cv2.destroyAllWindows()
print("✅ Программа завершена")