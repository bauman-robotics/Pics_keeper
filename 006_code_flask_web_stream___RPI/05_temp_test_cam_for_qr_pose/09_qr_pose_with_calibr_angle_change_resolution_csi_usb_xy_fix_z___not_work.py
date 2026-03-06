import cv2

import numpy as np
import re
from collections import deque
from picamera2 import Picamera2
import time

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
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# CAMERA_WIDTH = 1280
# CAMERA_HEIGHT = 720

#CAMERA_WIDTH = 1536
#CAMERA_HEIGHT = 864

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

# ===== КОРРЕКЦИЯ ЦВЕТОВ =====
# Для USB камер часто нужно преобразование
COLOR_CORRECTION = {
    'usb': 'RGB2BGR',  # USB камеры часто отдают RGB
    'csi': 'NONE'      # CSI через Picamera2 уже отдает BGR
}

# ===== ЗАГРУЗКА КАЛИБРОВКИ =====
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load(CAMERA_MATRIX_FILE)
dist_coeffs = np.load(DIST_COEFFS_FILE)
print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С QR =====
def parse_qr_data(data):
    """Извлекает размер из строки формата '25mm_M1'"""
    try:
        match = re.match(r'^([\d.]+)(mm|cm|m)_', data)
        if not match:
            return None
        value, unit = match.groups()
        value = float(value)
        if unit == 'mm':
            # Для мм: просто переводим в метры (делим на 1000)
            # Если в QR код зашита ПОЛОВИНА реального размера, то нужно умножать на 2
            # Но сейчас у вас 25mm в QR, а реально 50mm, значит нужно умножать на 2!
            return (value * 2) / 1000.0  # 25 * 2 / 1000 = 0.05 м (50 мм)
        elif unit == 'cm':
            return value / 100.0
        elif unit == 'm':
            return value
    except:
        return None

# def get_3d_model_points(marker_size_meters):
#     """Создает 3D-точки углов QR-кода"""
#     half = marker_size_meters / 2.0
#     return np.array([
#         [-half,  half, 0],
#         [ half,  half, 0],
#         [ half, -half, 0],
#         [-half, -half, 0]
#     ], dtype=np.float32)
#    ], dtype=np.float32) * -1  # умножаем все на -1

# def get_3d_model_points(marker_size_meters):
#     """Создает 3D-точки углов QR-кода (по часовой стрелке)"""
#     half = marker_size_meters / 2.0
#     return np.array([
#         [-half,  half, 0],  # верхний левый
#         [-half, -half, 0],  # нижний левый (изменено)
#         [ half, -half, 0],  # нижний правый
#         [ half,  half, 0]   # верхний правый (изменено)
#     ], dtype=np.float32)

# def get_3d_model_points(marker_size_meters):
#     """Создает 3D-точки углов QR-кода с нормалью, направленной НА камеру"""
#     half = marker_size_meters / 2.0
#     return np.array([
#         [-half,  half, 0],  # верхний левый
#         [ half,  half, 0],  # верхний правый
#         [ half, -half, 0],  # нижний правый
#         [-half, -half, 0]   # нижний левый
#     ], dtype=np.float32) * np.array([1, 1, -1])  # Инвертируем только Z!

def get_3d_model_points(marker_size_meters):
    """Создает 3D-точки углов QR-кода с учетом системы координат OpenCV"""
    half = marker_size_meters / 2.0
    return np.array([
        [-half, -half, 0],  # верхний левый (Y инвертирован!)
        [ half, -half, 0],  # верхний правый (Y инвертирован!)
        [ half,  half, 0],  # нижний правый (Y инвертирован!)
        [-half,  half, 0]   # нижний левый (Y инвертирован!)
    ], dtype=np.float32)



# def rotation_vector_to_euler_angles(rvec):
#     """Преобразует вектор Родрига в углы Эйлера"""
#     rotation_matrix, _ = cv2.Rodrigues(rvec)
    
#     sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
#     singular = sy < 1e-6
    
#     if not singular:
#         roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2])
#         pitch = np.arctan2(-rotation_matrix[2,0], sy)
#         yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0])
#     else:
#         roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1])
#         pitch = np.arctan2(-rotation_matrix[2,0], sy)
#         yaw = 0
    
#     roll_deg = np.degrees(roll)
#     pitch_deg = np.degrees(pitch)
#     yaw_deg = np.degrees(yaw)
    
#     # Нормализация углов
#     if roll_deg > 90:
#         roll_deg = roll_deg - 180
#     elif roll_deg < -90:
#         roll_deg = roll_deg + 180
    
#     if yaw_deg > 180:
#         yaw_deg -= 360
#     elif yaw_deg < -180:
#         yaw_deg += 360
    
#     return roll_deg, pitch_deg, yaw_deg


def normalize_angles(roll, pitch, yaw):
    """Нормализует углы в диапазон [-180, 180]"""
    def norm(a):
        while a > 180:
            a -= 360
        while a < -180:
            a += 360
        return a
    return norm(roll), norm(pitch), norm(yaw)

def draw_orientation_debug(frame, rvec, tvec, camera_matrix, dist_coeffs, marker_size):
    """Рисует оси маркера с подписями и проверкой границ"""
    h, w = frame.shape[:2]
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    
    try:
        # Центр маркера
        center_3d = np.array([[0, 0, 0]], dtype=np.float32)
        center_2d, _ = cv2.projectPoints(center_3d, rvec, tvec, camera_matrix, dist_coeffs)
        center = (int(center_2d[0][0][0]), int(center_2d[0][0][1]))  # Явное преобразование в int
        
        # Проверяем, что центр в пределах кадра
        if 0 <= center[0] < w and 0 <= center[1] < h:
            # Концы осей
            axis_length = marker_size / 2
            axes_3d = np.array([
                [axis_length, 0, 0],
                [0, axis_length, 0],
                [0, 0, axis_length]
            ], dtype=np.float32)
            
            axes_2d, _ = cv2.projectPoints(axes_3d, rvec, tvec, camera_matrix, dist_coeffs)
            
            # Рисуем оси
            colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # BGR: X-красный, Y-зеленый, Z-синий
            names = ['X', 'Y', 'Z']
            
            for i, end_2d in enumerate(axes_2d):
                # Явное преобразование в кортеж целых чисел
                end = (int(end_2d[0][0]), int(end_2d[0][1]))
                
                # Проверяем, что конечная точка в пределах кадра
                if 0 <= end[0] < w and 0 <= end[1] < h:
                    cv2.line(frame, center, end, colors[i], 2)
                    cv2.putText(frame, names[i], (end[0]+5, end[1]+5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i], 2)
    except Exception as e:
        #print(f"Ошибка в draw_orientation_debug: {e}")
        pass  # Игнорируем любые ошибки при рисовании
    
    return rotation_matrix[:, 0], rotation_matrix[:, 1], rotation_matrix[:, 2]

def rotation_vector_to_euler_angles(rvec):
    """Преобразует вектор Родрига в углы Эйлера для OpenCV с Y инвертированным в 3D модели"""
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    
    # Для вашей 3D модели (с инвертированным Y) и OpenCV камеры (X→, Y↓, Z→)
    # Используем другой порядок извлечения углов
    
    sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
    
    if sy > 1e-6:
        # Измененный порядок: сначала yaw, потом pitch, потом roll
        yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0])      # вокруг Z
        pitch = np.arctan2(-rotation_matrix[2,0], sy)                     # вокруг Y
        roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2])     # вокруг X
    else:
        yaw = 0
        pitch = np.arctan2(-rotation_matrix[2,0], sy)
        roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1])
    
    # Конвертируем в градусы
    roll = np.degrees(roll)
    pitch = np.degrees(pitch)
    yaw = np.degrees(yaw)
    
    # КОРРЕКТИРОВКА для Y инвертированного в 3D модели
    # Это превращает 168° в 12°, -43° в 43° и т.д.
    if abs(roll) > 90:
        # Маркер кажется перевернутым из-за Y инверсии
        roll = roll - 180 if roll > 0 else roll + 180
        pitch = -pitch
        yaw = -yaw
    
    # Финальная нормализация
    roll = ((roll + 180) % 360) - 180
    pitch = ((pitch + 180) % 360) - 180
    yaw = ((yaw + 180) % 360) - 180
    
    return roll, pitch, yaw

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
        # CSI камеры через Picamera2 уже отдают BGR
        return frame

def normalize_angles(roll, pitch, yaw):
    """Нормализует углы в диапазон [-180, 180]"""
    roll = ((roll + 180) % 360) - 180
    pitch = ((pitch + 180) % 360) - 180
    yaw = ((yaw + 180) % 360) - 180
    return roll, pitch, yaw

def diagnose_orientation(frame, camera_matrix, dist_coeffs, rvec, tvec, marker_size):
    """Диагностика ориентации маркера"""
    
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
    
    # Добавляем информационный текст
    status = "To_cam" if dot_z > 0 else "From_cam"
    color = (0, 255, 0) if dot_z > 0 else (0, 0, 255)
    
    cv2.putText(frame, f"Z-axis: {status}", (10, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"Z_direction: {dot_z:.2f}", (10, 270),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return dot_z > 0  # True если нормаль смотрит на камеру

def reinterpret_angles(roll, pitch, yaw, normal_direction):
    """Приводит углы к интуитивному стандарту"""
    # Если нормаль смотрит ОТ камеры (странно для маркера лицом к камере)
    if normal_direction == "ОТ камеры ⚠️":
        # Инвертируем всё
        roll = (roll + 180) % 360
        pitch = -pitch
        yaw = -yaw
    
    # Нормализуем roll в диапазон [-180, 180]
    if roll > 180:
        roll -= 360
    
    # Приводим pitch к диапазону [-90, 90] (более интуитивно)
    if pitch > 90:
        pitch = 180 - pitch
    elif pitch < -90:
        pitch = -180 - pitch
    
    return roll, pitch, yaw

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
        
        # Явно указываем BGR формат
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "BGR888"},
            controls={"FrameRate": CAMERA_FPS},
            buffer_count=4
        )
        
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        
        print(f"✅ CSI камера инициализирована")
        print(f"   Разрешение: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
        print(f"   Формат: BGR888 (совместим с OpenCV)")
        
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
    scale_x = width / CALIB_WIDTH
    scale_y = height / CALIB_HEIGHT
    
    camera_matrix_scaled = camera_matrix.copy()
    camera_matrix_scaled[0,0] *= scale_x
    camera_matrix_scaled[1,1] *= scale_y
    camera_matrix_scaled[0,2] *= scale_x
    camera_matrix_scaled[1,2] *= scale_y
    
    print(f"✅ Параметры отмасштабированы")
    print(f"   fx = {camera_matrix_scaled[0,0]:.1f}, fy = {camera_matrix_scaled[1,1]:.1f}")
    
    camera_matrix = camera_matrix_scaled

# ===== ТЕСТОВЫЙ ЗАХВАТ С КОРРЕКЦИЕЙ ЦВЕТОВ =====
print(f"\n📸 ТЕСТОВЫЙ ЗАХВАТ (3 кадра)")
print("="*50)

qr_detector = cv2.QRCodeDetector()

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
            # Picamera2 уже отдает BGR, коррекция не нужна
            print(f"   ✅ Кадр {i+1}: успешно, размер={frame.shape}")
            if i == 0:
                cv2.imwrite('test_frame_csi.jpg', frame)
                print(f"      Сохранен как test_frame_csi.jpg")
        else:
            print(f"   ❌ Кадр {i+1}: не получен")
    time.sleep(0.1)

# ===== ОСНОВНОЙ ЦИКЛ С КОРРЕКЦИЕЙ ЦВЕТОВ =====
print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {width}x{height}")
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print(f"   Коррекция цветов: {COLOR_CORRECTION[CAMERA_TYPE]}\n")

# ===== ОСНОВНОЙ ЦИКЛ =====
print(f"\n🚀 ЗАПУСК ДЕТЕКТИРОВАНИЯ")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {width}x{height}")
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print("   Используется конвертация RGB2BGR (как в рабочем файле)\n")

qr_detector = cv2.QRCodeDetector()
frame_count = 0

while True:
    # Захват кадра
    if CAMERA_TYPE.lower() == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        # Для USB может тоже нужна конвертация
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:  # CSI
        frame = picam2.capture_array()
        if frame is None:
            continue
        # ===== ВАЖНО: ТОЧНО КАК В РАБОЧЕМ ФАЙЛЕ =====
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
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
                # Получаем матрицу поворота для отладки
                rotation_matrix, _ = cv2.Rodrigues(rvec)
                print(f"\n📊 Матрица поворота:")
                print(f"  [{rotation_matrix[0,0]:.3f} {rotation_matrix[0,1]:.3f} {rotation_matrix[0,2]:.3f}]")
                print(f"  [{rotation_matrix[1,0]:.3f} {rotation_matrix[1,1]:.3f} {rotation_matrix[1,2]:.3f}]")
                print(f"  [{rotation_matrix[2,0]:.3f} {rotation_matrix[2,1]:.3f} {rotation_matrix[2,2]:.3f}]")

                # Получаем углы и нормализуем их
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                roll, pitch, yaw = normalize_angles(roll, pitch, yaw)
                # 👇 УДАЛИТЕ ЭТУ СТРОКУ:
                # roll, pitch, yaw = reinterpret_angles(roll, pitch, yaw, normal_direction)
                
                # Получаем нормаль (ось Z маркера)
                normal = get_plane_normal_from_rvec(rvec)
                normal_length = np.linalg.norm(normal)
                
                # Вектор от камеры к маркеру
                to_marker = tvec.flatten()
                to_marker_normalized = to_marker / np.linalg.norm(to_marker)
                
                # Проверяем, куда направлена нормаль
                dot_normal = np.dot(normal, to_marker_normalized)
                
                # Инвертируем нормаль если смотрит от камеры (для интуитивности)
                if dot_normal < 0:
                    normal_direction = "ОТ камеры ⚠️"
                    normal_for_display = -normal
                    dot_fixed = np.dot(normal_for_display, to_marker_normalized)
                else:
                    normal_direction = "К КАМЕРЕ ✅"
                    normal_for_display = normal
                    dot_fixed = dot_normal
                
                # Извлекаем смещения по X и Y
                offset_x = tvec[0][0] if tvec.shape == (3, 1) else tvec[0]
                offset_y = tvec[1][0] if tvec.shape == (3, 1) else tvec[1]
                distance = np.linalg.norm(tvec)
                
                # Вызываем дебаг-визуализацию осей
                x_axis, y_axis, z_axis = draw_orientation_debug(
                    frame, rvec, tvec, camera_matrix, dist_coeffs, marker_size
                )
                
                # Печатаем всю информацию в консоль
                print(f"\n📌 Распознан код: {data}")
                print(f"  📏 Размер маркера: {marker_size*1000:.1f} мм")
                print(f"  📏 Расстояние: {distance:.3f} м")
                print(f"  ↔️ Смещение X: {offset_x:.3f} м ({offset_x*1000:.1f} мм)")
                print(f"  ↕️ Смещение Y: {offset_y:.3f} м ({offset_y*1000:.1f} мм)")
                print(f"  🔄 Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
                print(f"  📐 Нормаль (raw): [{normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f}], длина={normal_length:.3f}")
                print(f"  🧭 Нормаль направлена: {normal_direction}")
                print(f"  📊 Скалярное произведение (raw): {dot_normal:.3f}")
                print(f"  📊 Скалярное произведение (исправленное): {dot_fixed:.3f}")
                print(f"  📍 Позиция: X={to_marker[0]:+.3f} м, Y={to_marker[1]:+.3f} м, Z={distance:.3f} м")
                
                # Выводим информацию на кадр
                y_pos = 30
                cv2.putText(frame, f"Dist: {distance:.2f}m", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                y_pos += 30
                cv2.putText(frame, f"X: {offset_x*1000:.1f}mm", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_pos += 30
                cv2.putText(frame, f"Y: {offset_y*1000:.1f}mm", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_pos += 30
                cv2.putText(frame, f"Roll: {roll:.1f}", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_pos += 30
                cv2.putText(frame, f"Pitch: {pitch:.1f}", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_pos += 30
                cv2.putText(frame, f"Yaw: {yaw:.1f}", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y_pos += 30
                
                # Добавляем информацию о направлении нормали
                normal_status = "↑" if dot_normal > 0 else "↓"
                cv2.putText(frame, f"Normal: {normal_status} {dot_normal:.2f}", (10, y_pos), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
    # Показываем кадр
    cv2.imshow('QR Pose Estimation', frame)
    
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