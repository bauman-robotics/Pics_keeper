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
#CAMERA_WIDTH = 640
#CAMERA_HEIGHT = 480

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

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
                # Получаем углы и расстояние
                roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                normal = get_plane_normal_from_rvec(rvec)
                distance = np.linalg.norm(tvec)
                
                print(f"\n📌 Распознан код: {data}")
                print(f"  📏 Расстояние: {distance:.3f} м")
                print(f"  🔄 Углы: roll={roll:.1f}°, pitch={pitch:.1f}°, yaw={yaw:.1f}°")
                
                # Рисуем оси
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