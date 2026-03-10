#!/usr/bin/env python3
"""
Детектирование и оценка позы AprilTag маркеров (tag36h11)
Адаптировано из скрипта для QR-кодов с сохранением структуры
Поддерживает USB и CSI камеры (Raspberry Pi Camera Module)
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
from collections import deque
from pyapriltags import Detector  # Заменяем QR на AprilTag

# ===== НАСТРОЙКИ =====
# Выбор типа камеры: 'usb' или 'csi'
CAMERA_TYPE = 'csi'  # 'usb' - для USB камер через V4L2, 'csi' - для CSI камер через Picamera2

# Для USB камер (V4L2)
USB_CAMERA_ID = 0  # индекс USB камеры (0, 1, 2...)
CAMERA_DEVICE = '/dev/video6'

# Для CSI камер (Picamera2)
CSI_CAMERA_ID = 0  # 0 - IMX708, 1 - IMX415

# ===== НАСТРОЙКИ =====
# Желаемое разрешение
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


CAMERA_FPS = 30

# Параметры калибровки
CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

# ===== НАСТРОЙКИ APRILTAG =====
MARKER_SIZE = 20  # размер в мм (20 мм для вашего маркера)
MARKER_FAMILY = 'tag36h11'  # семейство AprilTag
MARKER_SIZE_M = MARKER_SIZE / 1000.0  # перевод в метры

WIN_SIZE_PERSENT = 100 # 80 процентов экрана

# ===== КОРРЕКЦИЯ ЦВЕТОВ =====
# Для USB камер часто нужно преобразование
COLOR_CORRECTION = {
    'usb': 'RGB2BGR',  # USB камеры часто отдают RGB
    'csi': 'RGB2BGR'   # CSI через Picamera2 отдает RGB, нужно в BGR
}

# ===== ЗАГРУЗКА КАЛИБРОВКИ =====
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load(CAMERA_MATRIX_FILE)
dist_coeffs = np.load(DIST_COEFFS_FILE)
print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С APRILTAG =====
def rotation_vector_to_euler_angles(rvec):
    """Преобразует вектор Родрига в углы Эйлера (замена функции из QR-скрипта)"""
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

def correct_colors(frame, camera_type):
    """Корректирует порядок цветов в зависимости от типа камеры"""
    if camera_type == 'usb':
        # USB камеры часто отдают RGB, конвертируем в BGR
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:
        # CSI камеры через Picamera2 отдают RGB, но мы уже сконвертировали!
        # Возвращаем как есть, без повторной конвертации
        return frame

def diagnose_orientation(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_size):
    """Диагностика ориентации маркера (оставлено из QR-скрипта)"""
    
    # Текущее положение осей (уже рисуется drawFrameAxes)
    
    # Добавим текст с пояснением направления синей оси
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    
    # Синяя ось (Z) - это третья колонка матрицы поворота
    z_axis = rotation_matrix[:, 2]
    
    # Вектор от камеры к маркеру
    to_marker = tvec.flatten()
    to_marker_normalized = to_marker / np.linalg.norm(to_marker)
    
    # Скалярное произведение (должно быть > 0 если ось Z смотрит на камеру)
    dot_z = np.dot(z_axis, to_marker_normalized)
    
    # Проецируем центр маркера и точку вдоль нормали для визуализации
    center_3d = np.array([[0, 0, 0]], dtype=np.float32)
    normal_end_3d = np.array([[0, 0, marker_size/2]], dtype=np.float32)  # Половина размера
    
    center_2d, _ = cv2.projectPoints(center_3d, rvec, tvec, camera_matrix, dist_coeffs)
    normal_end_2d, _ = cv2.projectPoints(normal_end_3d, rvec, tvec, camera_matrix, dist_coeffs)
    
    center = tuple(center_2d[0][0].astype(int))
    normal_end = tuple(normal_end_2d[0][0].astype(int))
    
    # Рисуем толстую синюю линию для наглядности
    cv2.line(frame, center, normal_end, (255, 0, 0), 3)
    cv2.circle(frame, normal_end, 5, (255, 0, 0), -1)
    
    return dot_z > 0  # True если нормаль смотрит на камеру

def flip_z_axis(rvec, tvec):
    """
    Инвертирует направление оси Z (меняет на противоположное)
    При этом положение маркера в пространстве не меняется
    """
    # Получаем матрицу поворота
    R, _ = cv2.Rodrigues(rvec)
    
    # Создаем матрицу для инверсии оси Z
    # Поворот на 180 градусов вокруг оси X
    # X -> X, Y -> -Y, Z -> -Z
    R_flip = np.array([
        [1,  0,  0],
        [0, -1,  0],
        [0,  0, -1]
    ])
    
    # Применяем инверсию
    R_corrected = R @ R_flip
    
    # Обратно в вектор Родрига
    rvec_corrected, _ = cv2.Rodrigues(R_corrected)
    
    # Важно: tvec не меняем, так как положение центра маркера то же самое
    return rvec_corrected, tvec

# ===== ИНИЦИАЛИЗАЦИЯ КАМЕРЫ =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print(f"   Коррекция цветов: {COLOR_CORRECTION[CAMERA_TYPE]}")

if CAMERA_TYPE.lower() == 'usb':
    # ===== USB КАМЕРА ЧЕРЕЗ V4L2 =====
    print(f"   Режим: USB/V4L2 (камера #{USB_CAMERA_ID})")
    
    cap = cv2.VideoCapture(USB_CAMERA_ID)
    if not cap.isOpened():
        print(f"❌ Ошибка: не удалось открыть USB камеру #{USB_CAMERA_ID}")
        exit()
    
    # Устанавливаем разрешение
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"✅ USB камера открыта")
    print(f"   Разрешение: {actual_width}x{actual_height}")
    
    width, height = actual_width, actual_height
    picam2 = None

elif CAMERA_TYPE.lower() == 'csi':
    # ===== CSI КАМЕРА ЧЕРЕЗ PICAMERA2 =====
    print(f"   Режим: CSI/Picamera2 (камера #{CSI_CAMERA_ID})")
    
    try:
        picam2 = Picamera2(CSI_CAMERA_ID)
        
        # ВАЖНО: используем RGB888, потом конвертируем в BGR
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            controls={
                "FrameRate": CAMERA_FPS,
                "AfMode": 2,  # 2 = непрерывный автофокус (continuous)
                "AfSpeed": 1  # 1 = быстрая скорость фокусировки
            },
            buffer_count=4
        )
        
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        
        print(f"✅ CSI камера инициализирована")
        print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
        print(f"   Формат: RGB888 (будет конвертирован в BGR), Автофокус: ВКЛЮЧЕН")
        
        width, height = CAMERA_WIDTH, CAMERA_HEIGHT
        cap = None
        
    except Exception as e:
        print(f"❌ Ошибка инициализации CSI камеры: {e}")
        exit()
else:
    print(f"❌ Неизвестный тип камеры: {CAMERA_TYPE}")
    exit()

# ===== МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ КАЛИБРОВКИ =====
print(f"\n🔄 МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ")
print("="*50)
print(f"   Калибровка: {CALIB_WIDTH}x{CALIB_HEIGHT}")
print(f"   Текущее: {width}x{height}")

if width != CALIB_WIDTH or height != CALIB_HEIGHT:
    # Используем ЕДИНЫЙ масштаб на основе ширины
    scale = width / CALIB_WIDTH  # 1280/640 = 2.0
    
    camera_matrix_scaled = camera_matrix.copy()
    camera_matrix_scaled[0,0] *= scale  # fx
    camera_matrix_scaled[1,1] *= scale  # fy (ВАЖНО: одинаковый масштаб!)
    camera_matrix_scaled[0,2] *= scale  # cx
    camera_matrix_scaled[1,2] *= scale  # cy
    
    print(f"✅ Параметры отмасштабированы с коэффициентом {scale:.3f}")
    print(f"   fx = {camera_matrix_scaled[0,0]:.1f}, fy = {camera_matrix_scaled[1,1]:.1f}")
    
    camera_matrix = camera_matrix_scaled

# ===== ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА =====
print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА")
print("="*50)
print(f"   Семейство: {MARKER_FAMILY}")
print(f"   Размер маркера: {MARKER_SIZE} мм ({MARKER_SIZE_M:.3f} м)")

# Создаем детектор AprilTag
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

# ===== ТЕСТОВЫЙ ЗАХВАТ С КОРРЕКЦИЕЙ ЦВЕТОВ =====
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
        else:
            print(f"   ❌ Кадр {i+1}: не получен")
    time.sleep(0.1)

# ===== ОСНОВНОЙ ЦИКЛ =====
print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ APRILTAG")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {width}x{height}")
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print(f"   Маркер: {MARKER_FAMILY}, {MARKER_SIZE} мм\n")

frame_count = 0

while True:
    # Захват кадра
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        frame = correct_colors(frame, CAMERA_TYPE)
    else:  # CSI
        frame = picam2.capture_array()
        if frame is None:
            continue
        # Конвертируем RGB в BGR для OpenCV
        #frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        frame = correct_colors(frame, CAMERA_TYPE)  # Используем функцию
    
    frame_count += 1
    
    # Конвертируем в градации серого для AprilTag
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Детектируем AprilTag маркеры с оценкой позы
    detections = at_detector.detect(
        gray,
        estimate_tag_pose=True,
        camera_params=[camera_matrix[0,0], camera_matrix[1,1], 
                      camera_matrix[0,2], camera_matrix[1,2]],
        tag_size=MARKER_SIZE_M
    )
    
    if detections:
        # Проходим по каждому обнаруженному маркеру
        for idx, detection in enumerate(detections):
            # Получаем углы текущего маркера
            corners = np.array(detection.corners, dtype=np.float32)
            
            # Рисуем контур для текущего маркера
            for j in range(4):
                pt1 = tuple(corners[j].astype(int))
                pt2 = tuple(corners[(j+1)%4].astype(int))
                cv2.line(frame, pt1, pt2, (0, 255, 0), 3)
            
            # Получаем данные о позе из детектора
            tag_id = detection.tag_id
            
            # Конвертируем rotation matrix в rotation vector для OpenCV
            rvec, _ = cv2.Rodrigues(detection.pose_R)
            tvec = np.array(detection.pose_t).reshape(3, 1)

            # Разворачиваем ось Z
            rvec, tvec = flip_z_axis(rvec, tvec)
            
            # Получаем углы и расстояние
            roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
            normal = get_plane_normal_from_rvec(rvec)
            distance = np.linalg.norm(tvec)
            
            # Извлекаем смещения по X и Y
            offset_x = tvec[0][0] if tvec.shape == (3, 1) else tvec[0]
            offset_y = tvec[1][0] if tvec.shape == (3, 1) else tvec[1]
            
            print(f"\n📌 Распознан AprilTag {idx+1}: ID={tag_id}")
            print(f"  📏 Расстояние: {distance:.3f} м")
            print(f"  ↔️ Смещение X: {offset_x:.3f} м")
            print(f"  ↕️ Смещение Y: {offset_y:.3f} м")
            print(f"  🔄 Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
            
            # Рисуем оси координат
            cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, MARKER_SIZE_M/2)
            
            # Диагностика направления нормали
            normal_towards_camera = diagnose_orientation(frame, camera_matrix, dist_coeffs, rvec, tvec, MARKER_SIZE_M)
            
            line_spacing = 35  # базовый интервал между строками
            y_offset = 30 + idx * 180  # увеличили отступ между маркерами

            # Отображаем информацию на кадре
            cv2.putText(frame, f"April{idx+1}: ID={tag_id}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.putText(frame, f"Dist: {distance:.2f}m", 
                    (10, y_offset + line_spacing),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.putText(frame, f"X: {offset_x:.2f}m Y: {offset_y:.2f}m", 
                    (10, y_offset + line_spacing * 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            cv2.putText(frame, f"R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}", 
                    (10, y_offset + line_spacing * 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    
    # Масштабируем окно под размер экрана
    scale_percent = WIN_SIZE_PERSENT
    width_display = int(frame.shape[1] * scale_percent / 100)
    height_display = int(frame.shape[0] * scale_percent / 100)
    frame_display = cv2.resize(frame, (width_display, height_display))

    # Показываем масштабированный кадр
    cv2.imshow('AprilTag Pose Estimation', frame_display)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ===== ОЧИСТКА =====
print("\n👋 Завершение...")
if CAMERA_TYPE.lower() == 'usb':
    cap.release()
else:
    picam2.stop()
cv2.destroyAllWindows()
print("✅ Программа завершена")