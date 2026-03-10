#!/usr/bin/env python3
"""
Объединенный скрипт для отрисовки 3D модели, привязанной к AprilTag маркеру
Поддерживает USB и CSI камеры (Raspberry Pi Camera Module)

export DISPLAY=:0

1. убить сессию:
screen -X -S bird_detector quit

cd /home/pi/projects/Hailo8_projects/Pics_keeper
source venv/bin/activate
cd 006_code_flask_web_stream___RPI/
python3 20_aprilTag_obj_viewer.py
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
from collections import deque
from pyapriltags import Detector
import signal
import sys

# ===== НАСТРОЙКИ =====
# Выбор типа камеры: 'usb' или 'csi'
CAMERA_TYPE = 'csi'  # 'usb' - для USB камер через V4L2, 'csi' - для CSI камер через Picamera2

# Для USB камер (V4L2)
USB_CAMERA_ID = 0  # индекс USB камеры (0, 1, 2...)
CAMERA_DEVICE = '/dev/video6'

# Для CSI камер (Picamera2)
CSI_CAMERA_ID = 0  # 0 - IMX708, 1 - IMX415

# ===== НАСТРОЙКИ РАЗРЕШЕНИЯ =====
CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864
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

# ===== НАСТРОЙКИ ОТОБРАЖЕНИЯ =====
WIN_SIZE_PERSENT = 100  # 80 процентов экрана
SHOW_SLIDERS = True  # Показывать слайдеры для ручной подстройки
TARGET_MARKER_ID = 3  # ID маркера, к которому привязываем модель

# ===== ПУТЬ К 3D МОДЕЛИ =====
MODEL_PATH = "model_simple.obj"

# ===== КОРРЕКЦИЯ ЦВЕТОВ =====
COLOR_CORRECTION = {
    'usb': 'RGB2BGR',  # USB камеры часто отдают RGB
    'csi': 'RGB2BGR'   # CSI через Picamera2 отдает RGB, нужно в BGR
}

# ===== КЛАСС ДЛЯ ЗАГРУЗКИ OBJ МОДЕЛИ =====
class OBJModel:
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.load_obj(filename)
        
    def load_obj(self, filename):
        """Load OBJ file with vertices and faces"""
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        parts = line.strip().split()
                        self.vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                    elif line.startswith('f '):
                        parts = line.strip().split()
                        face = []
                        for part in parts[1:]:
                            idx = part.split('/')[0]
                            if idx:
                                face.append(int(idx) - 1)
                        if len(face) >= 3:
                            self.faces.append(face)
            
            self.vertices = np.array(self.vertices, dtype=np.float32)
            print(f"✅ Загружено {len(self.vertices)} вершин, {len(self.faces)} граней")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки OBJ: {e}")
    
    def transform(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
        """Apply transformations to vertices"""
        if len(self.vertices) == 0:
            return None
            
        transformed = self.vertices.copy()
        
        # Scale
        transformed *= scale
        
        # Rotation matrices
        if rot_x != 0:
            rad = np.radians(rot_x)
            rot_x_mat = np.array([
                [1, 0, 0],
                [0, np.cos(rad), -np.sin(rad)],
                [0, np.sin(rad), np.cos(rad)]
            ])
            transformed = transformed @ rot_x_mat.T
        
        if rot_y != 0:
            rad = np.radians(rot_y)
            rot_y_mat = np.array([
                [np.cos(rad), 0, np.sin(rad)],
                [0, 1, 0],
                [-np.sin(rad), 0, np.cos(rad)]
            ])
            transformed = transformed @ rot_y_mat.T
        
        if rot_z != 0:
            rad = np.radians(rot_z)
            rot_z_mat = np.array([
                [np.cos(rad), -np.sin(rad), 0],
                [np.sin(rad), np.cos(rad), 0],
                [0, 0, 1]
            ])
            transformed = transformed @ rot_z_mat.T
        
        # Translation
        transformed[:, 0] += offset_x
        transformed[:, 1] += offset_y
        transformed[:, 2] += offset_z
        
        return transformed

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С APRILTAG =====
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

def flip_z_axis(rvec, tvec):
    """
    Инвертирует направление оси Z (меняет на противоположное)
    При этом положение маркера в пространстве не меняется
    """
    R, _ = cv2.Rodrigues(rvec)
    
    R_flip = np.array([
        [1,  0,  0],
        [0, -1,  0],
        [0,  0, -1]
    ])
    
    R_corrected = R @ R_flip
    rvec_corrected, _ = cv2.Rodrigues(R_corrected)
    
    return rvec_corrected, tvec

def correct_colors(frame, camera_type):
    """Корректирует порядок цветов в зависимости от типа камеры"""
    if camera_type == 'usb':
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:
        return frame

def nothing(x):
    pass

def signal_handler(sig, frame):
    print("\n👋 Завершение работы...")
    cv2.destroyAllWindows()
    sys.exit(0)

# ===== ЗАГРУЗКА КАЛИБРОВКИ =====
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load(CAMERA_MATRIX_FILE)
dist_coeffs = np.load(DIST_COEFFS_FILE)
print(f"✅ Матрица камеры загружена (для {CALIB_WIDTH}x{CALIB_HEIGHT}):")
print(f"   fx = {camera_matrix[0,0]:.1f}, fy = {camera_matrix[1,1]:.1f}")
print(f"   cx = {camera_matrix[0,2]:.1f}, cy = {camera_matrix[1,2]:.1f}")

# ===== ИНИЦИАЛИЗАЦИЯ КАМЕРЫ =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)
print(f"   Тип камеры: {CAMERA_TYPE.upper()}")
print(f"   Коррекция цветов: {COLOR_CORRECTION[CAMERA_TYPE]}")

if CAMERA_TYPE.lower() == 'usb':
    print(f"   Режим: USB/V4L2 (камера #{USB_CAMERA_ID})")
    
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

elif CAMERA_TYPE.lower() == 'csi':
    print(f"   Режим: CSI/Picamera2 (камера #{CSI_CAMERA_ID})")
    
    try:
        picam2 = Picamera2(CSI_CAMERA_ID)
        
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            controls={
                "FrameRate": CAMERA_FPS,
                "AfMode": 2,
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
else:
    print(f"❌ Неизвестный тип камеры: {CAMERA_TYPE}")
    exit()

# ===== МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ КАЛИБРОВКИ =====
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

# ===== ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА =====
print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА")
print("="*50)
print(f"   Семейство: {MARKER_FAMILY}")
print(f"   Размер маркера: {MARKER_SIZE} мм ({MARKER_SIZE_M:.3f} м)")
print(f"   Целевой ID маркера: {TARGET_MARKER_ID}")

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

# ===== ЗАГРУЗКА 3D МОДЕЛИ =====
print(f"\n🎨 ЗАГРУЗКА 3D МОДЕЛИ")
print("="*50)
print(f"   Файл: {MODEL_PATH}")

model = OBJModel(MODEL_PATH)
if len(model.vertices) == 0:
    print("❌ Не удалось загрузить модель")
    exit()

# Предвычисление ребер для отрисовки
print("   Предвычисление ребер...")
edges = set()
for face in model.faces:
    for i in range(len(face)):
        edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
        edges.add(edge)
edges = list(edges)
print(f"✅ Вычислено {len(edges)} ребер")

# ===== СОЗДАНИЕ ОКНА И СЛАЙДЕРОВ =====
window_name = 'AprilTag 3D Model Viewer'
cv2.namedWindow(window_name)

if SHOW_SLIDERS:
    print(f"\n🎚️ СОЗДАНИЕ СЛАЙДЕРОВ РУЧНОЙ ПОДСТРОЙКИ")
    print("="*50)
    
    cv2.createTrackbar('Scale', window_name, 30, 100, nothing)
    cv2.createTrackbar('Rot X', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Y', window_name, 180, 360, nothing)
    cv2.createTrackbar('Rot Z', window_name, 180, 360, nothing)
    cv2.createTrackbar('Offset X', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Y', window_name, 500, 1000, nothing)
    cv2.createTrackbar('Offset Z', window_name, 300, 1000, nothing)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_name, 1, 2, nothing)
    
    print("✅ Слайдеры созданы")
    print("   Используйте слайдеры для точной подстройки положения модели")
    print("   относительно маркера")

print("\n🚀 ЗАПУСК ОСНОВНОГО ЦИКЛА")
print("="*50)
print("   Нажмите 'q' для выхода")
print(f"   Разрешение: {width}x{height}")
print(f"   Целевой ID маркера: {TARGET_MARKER_ID}")
if SHOW_SLIDERS:
    print("   Слайдеры: ВКЛ (используйте для подстройки)")
else:
    print("   Слайдеры: ВЫКЛ")
print("")

# Для FPS
last_time = time.time()
frame_count = 0
fps = 0

# Для хранения последней известной позиции маркера
last_known_rvec = None
last_known_tvec = None
marker_detected = False

# Обработчик сигналов
signal.signal(signal.SIGINT, signal_handler)

try:
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
            frame = correct_colors(frame, CAMERA_TYPE)
        
        frame_count += 1
        
        # Расчет FPS
        if frame_count % 10 == 0:
            current_time = time.time()
            fps = 10 / (current_time - last_time)
            last_time = current_time
        
        # Конвертируем в градации серого для AprilTag
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Детектируем AprilTag маркеры
        detections = at_detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=[camera_matrix[0,0], camera_matrix[1,1], 
                          camera_matrix[0,2], camera_matrix[1,2]],
            tag_size=MARKER_SIZE_M
        )
        
        # Переменные для хранения позиции целевого маркера
        target_rvec = None
        target_tvec = None
        current_tag_id = None
        
        # Обработка детекций
        if detections:
            for detection in detections:
                # Рисуем контуры всех маркеров
                corners = np.array(detection.corners, dtype=np.float32)
                for j in range(4):
                    pt1 = tuple(corners[j].astype(int))
                    pt2 = tuple(corners[(j+1)%4].astype(int))
                    
                    # Разные цвета для целевого и других маркеров
                    if detection.tag_id == TARGET_MARKER_ID:
                        color = (0, 255, 255)  # Желтый для целевого
                    else:
                        color = (0, 255, 0)    # Зеленый для остальных
                    
                    cv2.line(frame, pt1, pt2, color, 3)
                
                # Получаем данные о позе
                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                
                # Разворачиваем ось Z
                rvec, tvec = flip_z_axis(rvec, tvec)
                
                # Если это целевой маркер, сохраняем его позицию
                if detection.tag_id == TARGET_MARKER_ID:
                    target_rvec = rvec.copy()
                    target_tvec = tvec.copy()
                    current_tag_id = detection.tag_id
                    marker_detected = True
                    
                    # Рисуем оси для целевого маркера
                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, MARKER_SIZE_M)
                    
                    # Получаем углы и расстояние
                    roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                    distance = np.linalg.norm(tvec)
                    
                    # Отображаем информацию о целевом маркере
                    info_y = 30
                    cv2.putText(frame, f"TARGET ID: {detection.tag_id}", (10, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    cv2.putText(frame, f"Dist: {distance:.2f}m", (10, info_y + 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(frame, f"R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}", 
                               (10, info_y + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Если целевой маркер не обнаружен, но был обнаружен ранее,
        # используем последнюю известную позицию
        if target_rvec is None and last_known_rvec is not None and last_known_tvec is not None:
            target_rvec = last_known_rvec
            target_tvec = last_known_tvec
            cv2.putText(frame, "⚠️ USING LAST KNOWN POSITION", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        elif target_rvec is not None:
            # Обновляем последнюю известную позицию
            last_known_rvec = target_rvec.copy()
            last_known_tvec = target_tvec.copy()
        
        # Отрисовка 3D модели, если есть позиция маркера
        if target_rvec is not None:
            # Получаем значения со слайдеров для ручной подстройки
            if SHOW_SLIDERS:
                scale = cv2.getTrackbarPos('Scale', window_name) / 100.0
                rot_x = cv2.getTrackbarPos('Rot X', window_name) - 180
                rot_y = cv2.getTrackbarPos('Rot Y', window_name) - 180
                rot_z = cv2.getTrackbarPos('Rot Z', window_name) - 180
                offset_x = (cv2.getTrackbarPos('Offset X', window_name) - 500) / 10.0
                offset_y = (cv2.getTrackbarPos('Offset Y', window_name) - 500) / 10.0
                offset_z = cv2.getTrackbarPos('Offset Z', window_name) / 10.0
                mode = cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
            else:
                # Значения по умолчанию
                scale = 0.3
                rot_x = 0
                rot_y = 0
                rot_z = 0
                offset_x = 0
                offset_y = 0
                offset_z = 0
                mode = 1  # Wireframe по умолчанию
            
            # Трансформируем модель относительно маркера
            transformed = model.transform(scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z)
            
            if transformed is not None:
                # Проецируем вершины
                img_points, _ = cv2.projectPoints(transformed, target_rvec, target_tvec, 
                                                  camera_matrix, dist_coeffs)
                img_points = np.int32(img_points).reshape(-1, 2)
                
                # Отрисовка в зависимости от режима
                if mode == 0:  # Points only
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 2, (0, 255, 255), -1)
                
                elif mode == 1:  # Wireframe
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
                    
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 1, (0, 255, 255), -1)
                
                else:  # mode == 2, Faces
                    for i, face in enumerate(model.faces):
                        if i % 3 != 0:
                            continue
                        if len(face) >= 3:
                            pts = []
                            valid = True
                            for idx in face[:3]:
                                if idx < len(img_points):
                                    pt = img_points[idx]
                                    if 0 <= pt[0] < width and 0 <= pt[1] < height:
                                        pts.append([pt[0], pt[1]])
                                    else:
                                        valid = False
                                        break
                            
                            if valid and len(pts) == 3:
                                pts = np.array(pts, np.int32)
                                cv2.fillPoly(frame, [pts], (100, 100, 255))
                    
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 255), 1)
        
        # Отображение информации
        info_lines = [
            f"FPS: {fps:.1f} | Camera: {CAMERA_TYPE.upper()}",
            f"Target Marker ID: {TARGET_MARKER_ID}",
            f"Status: {'✅ DETECTED' if marker_detected else '❌ NOT DETECTED'}"
        ]
        
        y_offset = height - 100
        for line in info_lines:
            cv2.putText(frame, line, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 25
        
        cv2.putText(frame, "Press 'q' to exit", (width - 200, height - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        
        # Масштабируем окно под размер экрана
        scale_percent = WIN_SIZE_PERSENT
        width_display = int(frame.shape[1] * scale_percent / 100)
        height_display = int(frame.shape[0] * scale_percent / 100)
        frame_display = cv2.resize(frame, (width_display, height_display))
        
        # Показываем кадр
        cv2.imshow(window_name, frame_display)
        
        # Обработка клавиш
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r') and SHOW_SLIDERS:  # Сброс слайдеров
            cv2.setTrackbarPos('Scale', window_name, 30)
            cv2.setTrackbarPos('Rot X', window_name, 180)
            cv2.setTrackbarPos('Rot Y', window_name, 180)
            cv2.setTrackbarPos('Rot Z', window_name, 180)
            cv2.setTrackbarPos('Offset X', window_name, 500)
            cv2.setTrackbarPos('Offset Y', window_name, 500)
            cv2.setTrackbarPos('Offset Z', window_name, 300)
            print("🔄 Слайдеры сброшены")

except Exception as e:
    print(f"❌ Ошибка: {e}")

finally:
    # ===== ОЧИСТКА =====
    print("\n👋 Завершение...")
    if CAMERA_TYPE.lower() == 'usb':
        if cap:
            cap.release()
    else:
        if picam2:
            picam2.stop()
    cv2.destroyAllWindows()
    print("✅ Программа завершена")