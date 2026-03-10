#!/usr/bin/env python3
"""
Объединенный скрипт для отрисовки 3D модели, привязанной к AprilTag маркеру
Поддерживает USB и CSI камеры (Raspberry Pi Camera Module)
С кнопками для сохранения конфигурации и отображением осей модели
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
import json
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
WIN_SIZE_PERSENT = 100  # размер окна
SHOW_SLIDERS = True  # Показывать слайдеры
TARGET_MARKER_ID = 3  # ID маркера для привязки модели

# ===== ПУТЬ К 3D МОДЕЛИ =====
MODEL_PATH = "model_simple.obj"
CONFIG_FILE = "model_position_config.json"  # Файл для сохранения настроек

# ===== КОРРЕКЦИЯ ЦВЕТОВ =====
COLOR_CORRECTION = {
    'usb': 'RGB2BGR',
    'csi': 'RGB2BGR'
}

# ===== КНОПКИ ИНТЕРФЕЙСА =====
BUTTONS = {
    'save': {'rect': None, 'label': '💾 SAVE', 'color': (0, 200, 0), 'hover': (0, 255, 0)},
    'reset': {'rect': None, 'label': '🔄 RESET', 'color': (200, 200, 0), 'hover': (255, 255, 0)},
    'exit': {'rect': None, 'label': '❌ EXIT', 'color': (0, 0, 200), 'hover': (0, 0, 255)}
}
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 40
BUTTON_SPACING = 10

# ===== КЛАСС ДЛЯ ЗАГРУЗКИ OBJ МОДЕЛИ =====
class OBJModel:
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.load_obj(filename)
        self.center = None
        self.size = None
        self.calculate_center_and_size()
        
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
    
    def calculate_center_and_size(self):
        """Calculate center and size of the model"""
        if len(self.vertices) > 0:
            self.center = np.mean(self.vertices, axis=0)
            self.size = np.max(self.vertices, axis=0) - np.min(self.vertices, axis=0)
            print(f"   Центр модели: ({self.center[0]:.3f}, {self.center[1]:.3f}, {self.center[2]:.3f})")
            print(f"   Размер модели: ({self.size[0]:.3f}, {self.size[1]:.3f}, {self.size[2]:.3f})")
    
    def transform(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z, 
                  invert_x=False, invert_y=False, invert_z=False):
        """Apply transformations to vertices with axis inversion"""
        if len(self.vertices) == 0:
            return None, None, None
            
        transformed = self.vertices.copy()
        
        # Scale
        transformed *= scale
        
        # Apply axis inversion
        if invert_x:
            transformed[:, 0] *= -1
        if invert_y:
            transformed[:, 1] *= -1
        if invert_z:
            transformed[:, 2] *= -1
        
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
        
        # Calculate axes endpoints for visualization
        # Axes in model space (centered at origin after transform)
        axis_length = np.max(self.size) * 0.5 * scale
        axes_model = np.array([
            [axis_length, 0, 0],  # X axis (red)
            [0, axis_length, 0],  # Y axis (green)
            [0, 0, axis_length]   # Z axis (blue)
        ])
        
        return transformed, axes_model, axis_length

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С КОНФИГУРАЦИЕЙ =====
def save_config(config_file, params):
    """Save configuration to JSON file"""
    try:
        with open(config_file, 'w') as f:
            json.dump(params, f, indent=4)
        print(f"💾 Конфигурация сохранена в {config_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения конфигурации: {e}")
        return False

def load_config(config_file):
    """Load configuration from JSON file"""
    if not os.path.exists(config_file):
        print(f"📄 Файл конфигурации {config_file} не найден, используются значения по умолчанию")
        return None
    
    try:
        with open(config_file, 'r') as f:
            params = json.load(f)
        print(f"📂 Конфигурация загружена из {config_file}")
        return params
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return None

def params_to_slider_values(params):
    """Convert configuration parameters to slider values"""
    slider_values = {}
    
    # Scale: от 0 до 100 -> от 0.001 до 2.0
    if 'scale' in params:
        scale = max(0.001, min(2.0, params['scale']))
        slider_values['Scale'] = int(scale * 50)  # 0.001*50=0.05, 2.0*50=100
    
    # Rotations: от -180 до 180 -> от 0 до 360
    for axis in ['rot_x', 'rot_y', 'rot_z']:
        if axis in params:
            angle = params[axis]
            while angle > 180:
                angle -= 360
            while angle < -180:
                angle += 360
            slider_values[axis.replace('rot_', 'Rot ').upper()] = int(angle + 180)
    
    # Offsets: от -50 до 50 -> от 0 до 1000
    for axis in ['offset_x', 'offset_y', 'offset_z']:
        if axis in params:
            offset = max(-50, min(50, params[axis]))
            slider_values[axis.replace('offset_', 'Offset ').upper()] = int((offset + 50) * 10)
    
    # Mode
    if 'mode' in params:
        slider_values['Mode: 0pts/1wire/2face'] = params['mode']
    
    # Axis inversion flags
    if 'invert_x' in params:
        slider_values['Invert X'] = 1 if params['invert_x'] else 0
    if 'invert_y' in params:
        slider_values['Invert Y'] = 1 if params['invert_y'] else 0
    if 'invert_z' in params:
        slider_values['Invert Z'] = 1 if params['invert_z'] else 0
    
    return slider_values

def slider_values_to_params(slider_values):
    """Convert slider values to configuration parameters"""
    params = {}
    
    # Scale: от 0 до 100 -> от 0.001 до 2.0
    if 'Scale' in slider_values:
        params['scale'] = slider_values['Scale'] / 50.0  # 0/50=0, 100/50=2.0
    
    # Rotations: от 0 до 360 -> от -180 до 180
    for slider_name, param_name in [('Rot X', 'rot_x'), ('Rot Y', 'rot_y'), ('Rot Z', 'rot_z')]:
        if slider_name in slider_values:
            angle = slider_values[slider_name] - 180
            while angle > 180:
                angle -= 360
            while angle < -180:
                angle += 360
            params[param_name] = angle
    
    # Offsets: от 0 до 1000 -> от -50 до 50
    for slider_name, param_name in [('Offset X', 'offset_x'), ('Offset Y', 'offset_y'), ('Offset Z', 'offset_z')]:
        if slider_name in slider_values:
            params[param_name] = (slider_values[slider_name] - 500) / 10.0
    
    # Mode
    if 'Mode: 0pts/1wire/2face' in slider_values:
        params['mode'] = slider_values['Mode: 0pts/1wire/2face']
    
    # Axis inversion flags
    if 'Invert X' in slider_values:
        params['invert_x'] = bool(slider_values['Invert X'])
    if 'Invert Y' in slider_values:
        params['invert_y'] = bool(slider_values['Invert Y'])
    if 'Invert Z' in slider_values:
        params['invert_z'] = bool(slider_values['Invert Z'])
    
    return params

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
    """Инвертирует направление оси Z"""
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
    """Корректирует порядок цветов"""
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

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С КНОПКАМИ =====
def init_buttons(frame_width):
    """Инициализация позиций кнопок"""
    start_x = frame_width - (BUTTON_WIDTH + BUTTON_SPACING) * 3
    y = 10
    
    BUTTONS['save']['rect'] = (start_x, y, start_x + BUTTON_WIDTH, y + BUTTON_HEIGHT)
    BUTTONS['reset']['rect'] = (start_x + BUTTON_WIDTH + BUTTON_SPACING, y, 
                                start_x + BUTTON_WIDTH * 2 + BUTTON_SPACING, y + BUTTON_HEIGHT)
    BUTTONS['exit']['rect'] = (start_x + (BUTTON_WIDTH + BUTTON_SPACING) * 2, y,
                               start_x + BUTTON_WIDTH * 3 + BUTTON_SPACING * 2, y + BUTTON_HEIGHT)

def draw_buttons(frame):
    """Отрисовка кнопок на кадре"""
    mouse_x, mouse_y = cv2.getWindowImageRect(window_name)[2] // 2, 0  # Заглушка, реальные координаты мыши
    
    for name, btn in BUTTONS.items():
        if btn['rect']:
            x1, y1, x2, y2 = btn['rect']
            
            # Проверяем наведение мыши
            if hasattr(draw_buttons, 'mouse_x') and hasattr(draw_buttons, 'mouse_y'):
                if x1 <= draw_buttons.mouse_x <= x2 and y1 <= draw_buttons.mouse_y <= y2:
                    color = btn['hover']
                else:
                    color = btn['color']
            else:
                color = btn['color']
            
            # Рисуем кнопку
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            
            # Текст кнопки
            text_size = cv2.getTextSize(btn['label'], cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            text_x = x1 + (BUTTON_WIDTH - text_size[0]) // 2
            text_y = y1 + (BUTTON_HEIGHT + text_size[1]) // 2
            cv2.putText(frame, btn['label'], (text_x, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

def mouse_callback(event, x, y, flags, param):
    """Обработчик событий мыши"""
    draw_buttons.mouse_x = x
    draw_buttons.mouse_y = y
    
    if event == cv2.EVENT_LBUTTONDOWN:
        for name, btn in BUTTONS.items():
            if btn['rect']:
                x1, y1, x2, y2 = btn['rect']
                if x1 <= x <= x2 and y1 <= y <= y2:
                    if name == 'save':
                        # Сохраняем конфигурацию
                        slider_values = {}
                        slider_values['Scale'] = cv2.getTrackbarPos('Scale (0-100)', window_name)
                        slider_values['Rot X'] = cv2.getTrackbarPos('Rot X', window_name)
                        slider_values['Rot Y'] = cv2.getTrackbarPos('Rot Y', window_name)
                        slider_values['Rot Z'] = cv2.getTrackbarPos('Rot Z', window_name)
                        slider_values['Offset X'] = cv2.getTrackbarPos('Offset X (-50..50)', window_name)
                        slider_values['Offset Y'] = cv2.getTrackbarPos('Offset Y (-50..50)', window_name)
                        slider_values['Offset Z'] = cv2.getTrackbarPos('Offset Z (0..100)', window_name)
                        slider_values['Invert X'] = cv2.getTrackbarPos('Invert X (0/1)', window_name)
                        slider_values['Invert Y'] = cv2.getTrackbarPos('Invert Y (0/1)', window_name)
                        slider_values['Invert Z'] = cv2.getTrackbarPos('Invert Z (0/1)', window_name)
                        slider_values['Mode: 0pts/1wire/2face'] = cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
                        
                        params_to_save = slider_values_to_params(slider_values)
                        save_config(CONFIG_FILE, params_to_save)
                        print("✅ Конфигурация сохранена по клику")
                        
                    elif name == 'reset':
                        # Сброс слайдеров
                        cv2.setTrackbarPos('Scale (0-100)', window_name, 30)
                        cv2.setTrackbarPos('Rot X', window_name, 180)
                        cv2.setTrackbarPos('Rot Y', window_name, 180)
                        cv2.setTrackbarPos('Rot Z', window_name, 180)
                        cv2.setTrackbarPos('Offset X (-50..50)', window_name, 500)
                        cv2.setTrackbarPos('Offset Y (-50..50)', window_name, 500)
                        cv2.setTrackbarPos('Offset Z (0..100)', window_name, 300)
                        cv2.setTrackbarPos('Invert X (0/1)', window_name, 0)
                        cv2.setTrackbarPos('Invert Y (0/1)', window_name, 0)
                        cv2.setTrackbarPos('Invert Z (0/1)', window_name, 0)
                        cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_name, 1)
                        print("🔄 Слайдеры сброшены по клику")
                        
                    elif name == 'exit':
                        print("👋 Выход по клику")
                        cv2.destroyAllWindows()
                        sys.exit(0)


def draw_model_axes(frame, camera_matrix, dist_coeffs, rvec, tvec, scale=1.0, axis_length_mult=2.0):
    """
    Рисует оси модели с увеличенной длиной для лучшей видимости
    
    Args:
        frame: кадр для отрисовки
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        rvec: вектор поворота маркера
        tvec: вектор смещения маркера
        scale: масштаб модели
        axis_length_mult: множитель длины осей (относительно размера маркера)
    """
    # Базовые точки осей в локальных координатах модели
    axis_length = MARKER_SIZE_M * axis_length_mult  # Длина осей в метрах
    
    # Точки для осей (начало в центре модели)
    axes_points = np.float32([
        [0, 0, 0],           # Центр
        [axis_length, 0, 0],  # X (красный)
        [0, axis_length, 0],  # Y (зеленый)
        [0, 0, axis_length]   # Z (синий)
    ]).reshape(-1, 1, 3)
    
    # Проецируем точки на плоскость изображения
    img_points, _ = cv2.projectPoints(axes_points, rvec, tvec, camera_matrix, dist_coeffs)
    img_points = np.int32(img_points).reshape(-1, 2)
    
    center = tuple(img_points[0])
    x_axis = tuple(img_points[1])
    y_axis = tuple(img_points[2])
    z_axis = tuple(img_points[3])
    
    # Рисуем толстые линии осей
    cv2.line(frame, center, x_axis, (0, 0, 255), 4)  # Красный - X
    cv2.line(frame, center, y_axis, (0, 255, 0), 4)  # Зеленый - Y
    cv2.line(frame, center, z_axis, (255, 0, 0), 4)  # Синий - Z
    
    # Рисуем кружки на концах осей для лучшей видимости
    cv2.circle(frame, x_axis, 6, (0, 0, 255), -1)
    cv2.circle(frame, y_axis, 6, (0, 255, 0), -1)
    cv2.circle(frame, z_axis, 6, (255, 0, 0), -1)
    cv2.circle(frame, center, 8, (255, 255, 255), -1)
    
    # Добавляем подписи осей
    cv2.putText(frame, "X", (x_axis[0] + 10, x_axis[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(frame, "Y", (y_axis[0] + 10, y_axis[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "Z", (z_axis[0] + 10, z_axis[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)


def draw_model_axes_with_arrows(frame, camera_matrix, dist_coeffs, rvec, tvec, scale=1.0):
    """
    Рисует оси модели со стрелками на концах
    """
    # Длина осей - 3 размера маркера для лучшей видимости
    axis_length = MARKER_SIZE_M * 3.0
    
    axes_points = np.float32([
        [0, 0, 0],
        [axis_length, 0, 0],
        [0, axis_length, 0],
        [0, 0, axis_length]
    ]).reshape(-1, 1, 3)
    
    img_points, _ = cv2.projectPoints(axes_points, rvec, tvec, camera_matrix, dist_coeffs)
    img_points = np.int32(img_points).reshape(-1, 2)
    
    center = tuple(img_points[0])
    x_end = tuple(img_points[1])
    y_end = tuple(img_points[2])
    z_end = tuple(img_points[3])
    
    # Функция для рисования стрелки
    def draw_arrow(img, start, end, color, thickness=3):
        cv2.line(img, start, end, color, thickness)
        # Рисуем наконечник стрелки
        arrow_length = int(np.linalg.norm(np.array(end) - np.array(start)) * 0.2)
        angle = np.arctan2(end[1] - start[1], end[0] - start[0])
        
        # Две линии под углом для наконечника
        for sign in [-1, 1]:
            tip_angle = angle + sign * np.pi / 6
            tip_end = (
                int(end[0] - arrow_length * np.cos(tip_angle)),
                int(end[1] - arrow_length * np.sin(tip_angle))
            )
            cv2.line(img, end, tip_end, color, thickness)
    
    # Рисуем оси со стрелками
    draw_arrow(frame, center, x_end, (0, 0, 255), 4)  # Красный X
    draw_arrow(frame, center, y_end, (0, 255, 0), 4)  # Зеленый Y
    draw_arrow(frame, center, z_end, (255, 0, 0), 4)  # Синий Z
    
    # Добавляем подписи
    cv2.putText(frame, "X", (x_end[0] + 15, x_end[1] - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.putText(frame, "Y", (y_end[0] + 15, y_end[1] - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(frame, "Z", (z_end[0] + 15, z_end[1] - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)


def draw_model_axes_from_vertices(frame, img_points, center_idx=None):
    """
    Рисует оси модели на основе ее спроецированных вершин
    
    Args:
        frame: кадр для отрисовки
        img_points: все спроецированные точки модели (N, 2)
        center_idx: индекс вершины, которая считается центром (если None, берем среднее)
    """
    if len(img_points) == 0:
        return
    
    # Находим центр модели
    if center_idx is not None and center_idx < len(img_points):
        center = tuple(img_points[center_idx])
    else:
        # Используем среднее арифметическое всех вершин как центр
        center_x = int(np.mean(img_points[:, 0]))
        center_y = int(np.mean(img_points[:, 1]))
        center = (center_x, center_y)
    
    # Находим крайние точки по каждой оси для определения направления
    # Ищем вершины, максимально удаленные от центра в каждом направлении
    vectors = img_points - np.array([center[0], center[1]])
    distances = np.linalg.norm(vectors, axis=1)
    
    # Инициализируем переменные
    x_pos = None
    x_neg = None
    y_pos = None
    y_neg = None
    z_pos = None
    
    if len(img_points) > 10:  # Если достаточно вершин
        # Ищем вершины в разных направлениях
        angles = np.arctan2(vectors[:, 1], vectors[:, 0])
        
        # Разбиваем на 8 секторов и ищем самые дальние
        sectors = 8
        sector_edges = []
        
        for i in range(sectors):
            angle_min = -np.pi + i * 2*np.pi/sectors
            angle_max = -np.pi + (i+1) * 2*np.pi/sectors
            
            mask = (angles >= angle_min) & (angles < angle_max)
            if np.any(mask):
                sector_indices = np.where(mask)[0]
                # Берем самую дальнюю вершину в секторе
                farthest_idx = sector_indices[np.argmax(distances[sector_indices])]
                sector_edges.append(farthest_idx)
        
        # Выбираем по одной вершине для каждой оси
        if len(sector_edges) >= 3:
            # X轴: примерно горизонтальные направления (секторы 0 и 4)
            x_indices = [idx for idx in sector_edges if abs(np.cos(angles[idx])) > 0.7]
            if len(x_indices) > 0:
                x_pos = max(x_indices, key=lambda idx: vectors[idx, 0])  # положительное X
                x_neg = min(x_indices, key=lambda idx: vectors[idx, 0])  # отрицательное X
            
            # Y轴: примерно вертикальные направления (секторы 2 и 6)
            y_indices = [idx for idx in sector_edges if abs(np.sin(angles[idx])) > 0.7]
            if len(y_indices) > 0:
                y_pos = max(y_indices, key=lambda idx: vectors[idx, 1])  # положительное Y
                y_neg = min(y_indices, key=lambda idx: vectors[idx, 1])  # отрицательное Y
            
            # Z轴: используем перпендикулярное направление
            if len(sector_edges) > 0:
                z_pos = sector_edges[len(sector_edges)//2]
    else:
        # Для простых моделей используем первые несколько вершин
        if len(img_points) > 1:
            x_pos = 1
        if len(img_points) > 2:
            y_pos = 2
        if len(img_points) > 3:
            z_pos = 3
        x_neg = None
        y_neg = None
    
    # Рисуем оси
    axis_length = 50  # Длина осей в пикселях для fallback
    
    # Положительное X (красный)
    if x_pos is not None and isinstance(x_pos, int) and x_pos < len(img_points):
        x_pos_point = tuple(img_points[x_pos])
        cv2.line(frame, center, x_pos_point, (0, 0, 255), 3)
        cv2.circle(frame, x_pos_point, 6, (0, 0, 255), -1)
        cv2.putText(frame, "X+", (x_pos_point[0] + 10, x_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        # Если нет явной вершины, рисуем вправо от центра
        x_pos_point = (center[0] + axis_length, center[1])
        cv2.line(frame, center, x_pos_point, (0, 0, 255), 3)
        cv2.circle(frame, x_pos_point, 6, (0, 0, 255), -1)
        cv2.putText(frame, "X+", (x_pos_point[0] + 10, x_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # Положительное Y (зеленый)
    if y_pos is not None and isinstance(y_pos, int) and y_pos < len(img_points):
        y_pos_point = tuple(img_points[y_pos])
        cv2.line(frame, center, y_pos_point, (0, 255, 0), 3)
        cv2.circle(frame, y_pos_point, 6, (0, 255, 0), -1)
        cv2.putText(frame, "Y+", (y_pos_point[0] + 10, y_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        y_pos_point = (center[0], center[1] - axis_length)
        cv2.line(frame, center, y_pos_point, (0, 255, 0), 3)
        cv2.circle(frame, y_pos_point, 6, (0, 255, 0), -1)
        cv2.putText(frame, "Y+", (y_pos_point[0] + 10, y_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Положительное Z (синий)
    if z_pos is not None and isinstance(z_pos, int) and z_pos < len(img_points):
        z_pos_point = tuple(img_points[z_pos])
        cv2.line(frame, center, z_pos_point, (255, 0, 0), 3)
        cv2.circle(frame, z_pos_point, 6, (255, 0, 0), -1)
        cv2.putText(frame, "Z+", (z_pos_point[0] + 10, z_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    else:
        # Для Z используем диагональное направление
        z_pos_point = (center[0] + axis_length//2, center[1] + axis_length//2)
        cv2.line(frame, center, z_pos_point, (255, 0, 0), 3)
        cv2.circle(frame, z_pos_point, 6, (255, 0, 0), -1)
        cv2.putText(frame, "Z+", (z_pos_point[0] + 10, z_pos_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    
    # Рисуем центр
    cv2.circle(frame, center, 8, (255, 255, 255), -1)
    cv2.putText(frame, "C", (center[0] + 10, center[1] - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Отрицательные направления (полупрозрачные)
    if x_neg is not None and isinstance(x_neg, int) and x_neg < len(img_points):
        x_neg_point = tuple(img_points[x_neg])
        overlay = frame.copy()
        cv2.line(overlay, center, x_neg_point, (0, 0, 255), 2)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        cv2.putText(frame, "X-", (x_neg_point[0] + 10, x_neg_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 1)
    
    if y_neg is not None and isinstance(y_neg, int) and y_neg < len(img_points):
        y_neg_point = tuple(img_points[y_neg])
        overlay = frame.copy()
        cv2.line(overlay, center, y_neg_point, (0, 255, 0), 2)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        cv2.putText(frame, "Y-", (y_neg_point[0] + 10, y_neg_point[1] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 1)

# ========================================================================================
# ========================================================================================

# ===== ЗАГРУЗКА КАЛИБРОВКИ =====
print("\n📷 ЗАГРУЗКА ПАРАМЕТРОВ КАЛИБРОВКИ")
print("="*50)
camera_matrix = np.load(CAMERA_MATRIX_FILE)
dist_coeffs = np.load(DIST_COEFFS_FILE)
print(f"✅ Матрица камеры загружена")

# ===== ИНИЦИАЛИЗАЦИЯ КАМЕРЫ =====
print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
print("="*50)

if CAMERA_TYPE.lower() == 'usb':
    cap = cv2.VideoCapture(USB_CAMERA_ID)
    if not cap.isOpened():
        print(f"❌ Ошибка: не удалось открыть USB камеру")
        exit()
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    width, height = actual_width, actual_height
    picam2 = None

elif CAMERA_TYPE.lower() == 'csi':
    try:
        picam2 = Picamera2(CSI_CAMERA_ID)
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": CAMERA_FPS, "AfMode": 2, "AfSpeed": 1},
            buffer_count=4
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        
        width, height = CAMERA_WIDTH, CAMERA_HEIGHT
        cap = None
        
    except Exception as e:
        print(f"❌ Ошибка инициализации CSI камеры: {e}")
        exit()
else:
    print(f"❌ Неизвестный тип камеры")
    exit()

print(f"✅ Камера инициализирована: {width}x{height}")

# ===== МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ КАЛИБРОВКИ =====
if width != CALIB_WIDTH or height != CALIB_HEIGHT:
    scale = width / CALIB_WIDTH
    camera_matrix_scaled = camera_matrix.copy()
    camera_matrix_scaled[0,0] *= scale
    camera_matrix_scaled[1,1] *= scale
    camera_matrix_scaled[0,2] *= scale
    camera_matrix_scaled[1,2] *= scale
    camera_matrix = camera_matrix_scaled
    print(f"✅ Параметры отмасштабированы с коэффициентом {scale:.3f}")

# ===== ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА =====
print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ APRILTAG ДЕТЕКТОРА")
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
model = OBJModel(MODEL_PATH)
if len(model.vertices) == 0:
    print("❌ Не удалось загрузить модель")
    exit()

# Предвычисление ребер
print("   Предвычисление ребер...")
edges = set()
for face in model.faces:
    for i in range(len(face)):
        edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
        edges.add(edge)
edges = list(edges)
print(f"✅ Вычислено {len(edges)} ребер")

# ===== ЗАГРУЗКА КОНФИГУРАЦИИ =====
print(f"\n⚙️ ЗАГРУЗКА КОНФИГУРАЦИИ")
config_params = load_config(CONFIG_FILE)

# ===== СОЗДАНИЕ ОКНА И СЛАЙДЕРОВ =====
window_name = 'AprilTag 3D Model Viewer'
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

if SHOW_SLIDERS:
    print(f"\n🎚️ СОЗДАНИЕ СЛАЙДЕРОВ")
    
    default_values = {}
    if config_params:
        default_values = params_to_slider_values(config_params)
    
    # Scale (0-100)
    default_scale = default_values.get('Scale', 30)
    cv2.createTrackbar('Scale (0-100)', window_name, default_scale, 100, nothing)
    
    # Rotations
    default_rot_x = default_values.get('Rot X', 180)
    default_rot_y = default_values.get('Rot Y', 180)
    default_rot_z = default_values.get('Rot Z', 180)
    cv2.createTrackbar('Rot X', window_name, default_rot_x, 360, nothing)
    cv2.createTrackbar('Rot Y', window_name, default_rot_y, 360, nothing)
    cv2.createTrackbar('Rot Z', window_name, default_rot_z, 360, nothing)
    
    # Offsets
    default_offset_x = default_values.get('Offset X', 500)
    default_offset_y = default_values.get('Offset Y', 500)
    default_offset_z = default_values.get('Offset Z', 300)
    cv2.createTrackbar('Offset X (-50..50)', window_name, default_offset_x, 1000, nothing)
    cv2.createTrackbar('Offset Y (-50..50)', window_name, default_offset_y, 1000, nothing)
    cv2.createTrackbar('Offset Z (0..100)', window_name, default_offset_z, 1000, nothing)
    
    # Axis inversion
    default_invert_x = default_values.get('Invert X', 0)
    default_invert_y = default_values.get('Invert Y', 0)
    default_invert_z = default_values.get('Invert Z', 0)
    cv2.createTrackbar('Invert X (0/1)', window_name, default_invert_x, 1, nothing)
    cv2.createTrackbar('Invert Y (0/1)', window_name, default_invert_y, 1, nothing)
    cv2.createTrackbar('Invert Z (0/1)', window_name, default_invert_z, 1, nothing)
    
    # Mode
    default_mode = default_values.get('Mode: 0pts/1wire/2face', 1)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_name, default_mode, 2, nothing)
    
    print("✅ Слайдеры созданы")

# Инициализация кнопок
init_buttons(width)

print("\n🚀 ЗАПУСК ОСНОВНОГО ЦИКЛА")
print("="*50)
print("   Используйте мышь для нажатия кнопок:")
print("   💾 SAVE - сохранить конфигурацию")
print("   🔄 RESET - сбросить слайдеры")
print("   ❌ EXIT - выход")
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
        else:
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
        
        # Детектируем AprilTag маркеры
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
        
        # Обработка детекций
        if detections:
            for detection in detections:
                # Рисуем контуры маркеров
                corners = np.array(detection.corners, dtype=np.float32)
                for j in range(4):
                    pt1 = tuple(corners[j].astype(int))
                    pt2 = tuple(corners[(j+1)%4].astype(int))
                    
                    if detection.tag_id == TARGET_MARKER_ID:
                        color = (0, 255, 255)  # Желтый для целевого
                    else:
                        color = (0, 255, 0)    # Зеленый для остальных
                    
                    cv2.line(frame, pt1, pt2, color, 3)
                
                # Получаем данные о позе
                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                rvec, tvec = flip_z_axis(rvec, tvec)
                
                # Если это целевой маркер
                if detection.tag_id == TARGET_MARKER_ID:
                    target_rvec = rvec.copy()
                    target_tvec = tvec.copy()
                    marker_detected = True
                    
                    # Рисуем оси маркера
                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, MARKER_SIZE_M)
                    
                    # Информация о маркере
                    roll, pitch, yaw = rotation_vector_to_euler_angles(rvec)
                    distance = np.linalg.norm(tvec)
                    
                    info_y = 30
                    cv2.putText(frame, f"TARGET ID: {detection.tag_id}", (10, info_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    cv2.putText(frame, f"Dist: {distance:.2f}m", (10, info_y + 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Используем последнюю известную позицию если нужно
        if target_rvec is None and last_known_rvec is not None:
            target_rvec = last_known_rvec
            target_tvec = last_known_tvec
            cv2.putText(frame, "⚠️ USING LAST KNOWN POSITION", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        elif target_rvec is not None:
            last_known_rvec = target_rvec.copy()
            last_known_tvec = target_tvec.copy()
        
        # Отрисовка 3D модели
        if target_rvec is not None and SHOW_SLIDERS:
            # Получаем значения слайдеров
            slider_values = {}
            slider_values['Scale'] = cv2.getTrackbarPos('Scale (0-100)', window_name)
            slider_values['Rot X'] = cv2.getTrackbarPos('Rot X', window_name)
            slider_values['Rot Y'] = cv2.getTrackbarPos('Rot Y', window_name)
            slider_values['Rot Z'] = cv2.getTrackbarPos('Rot Z', window_name)
            slider_values['Offset X'] = cv2.getTrackbarPos('Offset X (-50..50)', window_name)
            slider_values['Offset Y'] = cv2.getTrackbarPos('Offset Y (-50..50)', window_name)
            slider_values['Offset Z'] = cv2.getTrackbarPos('Offset Z (0..100)', window_name)
            slider_values['Invert X'] = cv2.getTrackbarPos('Invert X (0/1)', window_name)
            slider_values['Invert Y'] = cv2.getTrackbarPos('Invert Y (0/1)', window_name)
            slider_values['Invert Z'] = cv2.getTrackbarPos('Invert Z (0/1)', window_name)
            slider_values['Mode: 0pts/1wire/2face'] = cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
            
            params = slider_values_to_params(slider_values)
            
            # Трансформируем модель
            transformed, axes_model, axis_length = model.transform(
                params['scale'], 
                params['rot_x'], params['rot_y'], params['rot_z'],
                params['offset_x'], params['offset_y'], params['offset_z'],
                params.get('invert_x', False),
                params.get('invert_y', False),
                params.get('invert_z', False)
            )
            
            if transformed is not None:

                #draw_model_axes(frame, camera_matrix, dist_coeffs, target_rvec, target_tvec, 
                #   scale=params['scale'], axis_length_mult=3.0)   

                # draw_model_axes_with_arrows(frame, camera_matrix, dist_coeffs, target_rvec, 
                #     target_tvec)                                

                # Проецируем вершины модели
                img_points, _ = cv2.projectPoints(transformed, target_rvec, target_tvec, 
                                                  camera_matrix, dist_coeffs)
                img_points = np.int32(img_points).reshape(-1, 2)
                
                # Проецируем оси модели
                axes_points, _ = cv2.projectPoints(axes_model, target_rvec, target_tvec,
                                                   camera_matrix, dist_coeffs)
                axes_points = np.int32(axes_points).reshape(-1, 2)
                
                # Рисуем оси модели (красный-X, зеленый-Y, синий-Z)
                origin = axes_points[0]  # Центр модели (0,0,0 после трансформации)
                cv2.line(frame, tuple(origin), tuple(axes_points[0]), (0, 0, 255), 3)  # X - красный
                cv2.line(frame, tuple(origin), tuple(axes_points[1]), (0, 255, 0), 3)  # Y - зеленый
                cv2.line(frame, tuple(origin), tuple(axes_points[2]), (255, 0, 0), 3)  # Z - синий
                
                # Рисуем модель в зависимости от режима
                mode = params['mode']
                
                if mode == 0:  # Points
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 2, (255, 255, 0), -1)
                
                elif mode == 1:  # Wireframe
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
                
                else:  # Faces
                    for face in model.faces:
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

                draw_model_axes_from_vertices(frame, img_points)


        # Отображение информации
        info_lines = [
            f"FPS: {fps:.1f}",
            f"Target ID: {TARGET_MARKER_ID}",
            f"Status: {'✅' if marker_detected else '❌'}"
        ]
        
        if SHOW_SLIDERS and 'params' in locals():
            info_lines.append(f"Scale: {params['scale']:.3f}")
        
        y_offset = height - 100
        for line in info_lines:
            cv2.putText(frame, line, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 25
        
        # Рисуем кнопки
        draw_buttons(frame)
        
        # Масштабируем окно
        scale_percent = WIN_SIZE_PERSENT
        width_display = int(frame.shape[1] * scale_percent / 100)
        height_display = int(frame.shape[0] * scale_percent / 100)
        frame_display = cv2.resize(frame, (width_display, height_display))
        
        cv2.imshow(window_name, frame_display)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except Exception as e:
    print(f"❌ Ошибка: {e}")

finally:
    print("\n👋 Завершение...")
    if CAMERA_TYPE.lower() == 'usb' and cap:
        cap.release()
    elif picam2:
        picam2.stop()
    cv2.destroyAllWindows()
    print("✅ Программа завершена")