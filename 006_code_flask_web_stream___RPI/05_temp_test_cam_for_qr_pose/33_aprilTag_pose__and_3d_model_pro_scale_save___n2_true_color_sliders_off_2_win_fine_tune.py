#!/usr/bin/env python3
"""
AprilTag 3D Model Viewer - Привязка 3D модели к AprilTag маркеру
Поддерживает USB и CSI камеры
Версия с двумя окнами: видео и управление

export DISPLAY=:0

1. убить сессию:
screen -X -S bird_detector quit

source /home/pi/projects/Hailo8_projects/Pics_keeper/venv/bin/activate
cd /home/pi/projects/Hailo8_projects/Pics_keeper/006_code_flask_web_stream___RPI/
python3 32_aprilTag_pose__and_3d_model_pro_scale_save___n2_true_color_sliders_off_2_win.py

deactivate
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import os
import json
from pyapriltags import Detector
import signal
import sys
import tkinter as tk  

# ===== НАСТРОЙКИ ОТОБРАЖЕНИЯ =====
# Автоматическое определение размера экрана
try:
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    
    # Коэффициент масштабирования (95% от экрана)
    DISPLAY_SCALE = 0.95
    DISPLAY_WIDTH = int(screen_width * DISPLAY_SCALE)
    DISPLAY_HEIGHT = int(screen_height * DISPLAY_SCALE)
    
    print(f"\n🖥️ РАЗРЕШЕНИЕ ЭКРАНА")
    print(f"{'='*50}")
    print(f"   Экран: {screen_width}x{screen_height}")
    print(f"   Окно: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT} ({DISPLAY_SCALE*100:.0f}%)")
except:
    DISPLAY_WIDTH = 1280
    DISPLAY_HEIGHT = 720
    print(f"\n⚠️ Не удалось определить размер экрана, используется {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

CAMERA_TYPE = 'csi'
CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864
CAMERA_FPS = 30

# Калибровка камеры
CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

# Параметры AprilTag
MARKER_SIZE = 20  # мм
MARKER_FAMILY = 'tag36h11'
TARGET_MARKER_ID = 3

# Файлы модели и конфигурации
MODEL_PATH = "model_simple.obj"
CONFIG_FILE = "model_position.json"

# ============================================================================
# КЛАСС ДЛЯ РАБОТЫ С 3D МОДЕЛЬЮ
# ============================================================================

class OBJModel:
    """Загрузка и трансформация 3D модели из OBJ файла"""
    
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.filename = filename
        self.load_obj(filename)
        
    def load_obj(self, filename):
        """Загрузка OBJ файла с вершинами и гранями"""
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        parts = line.strip().split()
                        self.vertices.append([
                            float(parts[1]) / 1000.0,  # X в метры
                            float(parts[2]) / 1000.0,  # Y в метры
                            float(parts[3]) / 1000.0   # Z в метры
                        ])
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
            
            # Вычисляем статистику модели
            self.min_bounds = np.min(self.vertices, axis=0)
            self.max_bounds = np.max(self.vertices, axis=0)
            self.center = (self.min_bounds + self.max_bounds) / 2
            self.size = self.max_bounds - self.min_bounds
            self.diagonal = np.linalg.norm(self.size)
            
            self._print_statistics()
            
        except Exception as e:
            print(f"❌ Ошибка загрузки OBJ: {e}")
            sys.exit(1)
    
    def _print_statistics(self):
        """Вывод статистики модели в консоль"""
        print(f"\n{'='*60}")
        print(f"📊 СТАТИСТИКА МОДЕЛИ: {os.path.basename(self.filename)}")
        print(f"{'='*60}")
        print(f"✅ Загружено: {len(self.vertices)} вершин, {len(self.faces)} граней")
        print(f"\n📐 ГАБАРИТЫ (в метрах, после перевода из мм):")
        print(f"   Min: ({self.min_bounds[0]:.4f}, {self.min_bounds[1]:.4f}, {self.min_bounds[2]:.4f})")
        print(f"   Max: ({self.max_bounds[0]:.4f}, {self.max_bounds[1]:.4f}, {self.max_bounds[2]:.4f})")
        print(f"   Center: ({self.center[0]:.4f}, {self.center[1]:.4f}, {self.center[2]:.4f})")
        print(f"   Size (ШxВxГ): {self.size[0]:.4f} x {self.size[1]:.4f} x {self.size[2]:.4f}")
        print(f"   Диагональ: {self.diagonal:.4f} м")
        print(f"{'='*60}")
    
    def get_transform_matrix(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
        """Создает матрицу трансформации 4x4 из параметров"""
        S = np.diag([scale, scale, scale, 1.0])
        
        Rx = np.eye(4)
        Ry = np.eye(4)
        Rz = np.eye(4)
        
        if rot_x != 0:
            rad = np.radians(rot_x)
            Rx[:3, :3] = [
                [1, 0, 0],
                [0, np.cos(rad), -np.sin(rad)],
                [0, np.sin(rad), np.cos(rad)]
            ]
        
        if rot_y != 0:
            rad = np.radians(rot_y)
            Ry[:3, :3] = [
                [np.cos(rad), 0, np.sin(rad)],
                [0, 1, 0],
                [-np.sin(rad), 0, np.cos(rad)]
            ]
        
        if rot_z != 0:
            rad = np.radians(rot_z)
            Rz[:3, :3] = [
                [np.cos(rad), -np.sin(rad), 0],
                [np.sin(rad), np.cos(rad), 0],
                [0, 0, 1]
            ]
        
        R = Rz @ Ry @ Rx
        T = np.eye(4)
        T[:3, 3] = [offset_x, offset_y, offset_z]
        
        return T @ R @ S
    
    def transform(self, transform_matrix):
        """Применяет матрицу трансформации к вершинам"""
        if len(self.vertices) == 0:
            return None
        
        vertices_h = np.hstack([self.vertices, np.ones((len(self.vertices), 1))])
        transformed_h = (transform_matrix @ vertices_h.T).T
        return transformed_h[:, :3]

# ============================================================================
# КЛАСС ДЛЯ КНОПОК ИНТЕРФЕЙСА
# ============================================================================

class Button:
    """Интерактивная кнопка для интерфейса"""
    
    def __init__(self, x, y, width, height, text, color=(100, 100, 200), hover_color=(150, 150, 255)):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        
    def draw(self, frame):
        """Отрисовка кнопки"""
        color = self.hover_color if self.is_hovered else self.color
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), color, -1)
        cv2.rectangle(frame, (self.x, self.y), (self.x + self.width, self.y + self.height), (255, 255, 255), 2)
        
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        text_x = self.x + (self.width - text_size[0]) // 2
        text_y = self.y + (self.height + text_size[1]) // 2
        cv2.putText(frame, self.text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
    def is_inside(self, x, y):
        """Проверка, находится ли точка внутри кнопки"""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С КОНФИГУРАЦИЕЙ
# ============================================================================

def save_config(config_file, params):
    """Сохранение конфигурации в JSON"""
    try:
        params_with_time = params.copy()
        params_with_time['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(config_file, 'w') as f:
            json.dump(params_with_time, f, indent=4)
        print(f"\n💾 Конфигурация сохранена в {config_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def load_config(config_file):
    """Загрузка конфигурации из JSON"""
    try:
        if not os.path.exists(config_file):
            print(f"\n⚠️ Файл {config_file} не найден")
            return None
            
        with open(config_file, 'r') as f:
            params = json.load(f)
        
        print(f"\n📂 Загружена конфигурация из {config_file}")
        return params
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

def slider_to_params(slider_values):
    """Преобразование значений слайдеров в параметры"""
    params = {}
    
    # Грубая настройка масштаба (логарифмическая шкала)
    if 'Scale_coarse' in slider_values:
        log_scale = -3 + (slider_values['Scale_coarse'] / 100) * 3.301
        params['scale'] = 10 ** log_scale
    
    # Точная настройка масштаба (относительная)
    if 'Scale_fine' in slider_values:
        fine_scale_factor = 1.0 + (slider_values['Scale_fine'] - 500) / 500.0 * 0.1  # ±10%
        if 'scale' in params:
            params['scale'] *= fine_scale_factor
    
    # Повороты: грубая настройка
    params['rot_x'] = slider_values.get('Rot X_coarse', 180) - 180
    params['rot_y'] = slider_values.get('Rot Y_coarse', 180) - 180
    params['rot_z'] = slider_values.get('Rot Z_coarse', 180) - 180
    
    # Повороты: точная настройка (±5 градусов)
    params['rot_x'] += (slider_values.get('Rot X_fine', 500) - 500) / 100.0 * 5
    params['rot_y'] += (slider_values.get('Rot Y_fine', 500) - 500) / 100.0 * 5
    params['rot_z'] += (slider_values.get('Rot Z_fine', 500) - 500) / 100.0 * 5
    
    # Смещения: грубая настройка
    params['offset_x'] = (slider_values.get('Offset X_coarse', 500) - 500) / 100.0
    params['offset_y'] = (slider_values.get('Offset Y_coarse', 500) - 500) / 100.0
    params['offset_z'] = (slider_values.get('Offset Z_coarse', 500) - 500) / 100.0
    
    # Смещения: точная настройка (±0.05 м)
    params['offset_x'] += (slider_values.get('Offset X_fine', 500) - 500) / 500.0 * 0.05
    params['offset_y'] += (slider_values.get('Offset Y_fine', 500) - 500) / 500.0 * 0.05
    params['offset_z'] += (slider_values.get('Offset Z_fine', 500) - 500) / 500.0 * 0.05
    
    params['mode'] = slider_values.get('Mode', 1)
    
    return params

def params_to_slider(params):
    """Преобразование параметров в значения слайдеров"""
    slider_values = {}
    
    # Масштаб
    if 'scale' in params:
        scale = max(0.001, min(2.0, params['scale']))
        log_scale = np.log10(scale)
        slider_values['Scale_coarse'] = int((log_scale + 3) * 100 / 3.301)
        slider_values['Scale_fine'] = 500  # Центр для точной настройки
    
    # Повороты - преобразуем в int
    slider_values['Rot X_coarse'] = int(params.get('rot_x', 0) + 180)
    slider_values['Rot Y_coarse'] = int(params.get('rot_y', 0) + 180)
    slider_values['Rot Z_coarse'] = int(params.get('rot_z', 0) + 180)
    slider_values['Rot X_fine'] = 500
    slider_values['Rot Y_fine'] = 500
    slider_values['Rot Z_fine'] = 500
    
    # Смещения - преобразуем в int
    slider_values['Offset X_coarse'] = int(params.get('offset_x', 0) * 100 + 500)
    slider_values['Offset Y_coarse'] = int(params.get('offset_y', 0) * 100 + 500)
    slider_values['Offset Z_coarse'] = int(params.get('offset_z', 0) * 100 + 500)
    slider_values['Offset X_fine'] = 500
    slider_values['Offset Y_fine'] = 500
    slider_values['Offset Z_fine'] = 500
    
    slider_values['Mode'] = int(params.get('mode', 1))
    
    return slider_values

# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С APRILTAG
# ============================================================================

def rotation_vector_to_euler(rvec):
    """Преобразование вектора Родрига в углы Эйлера"""
    R, _ = cv2.Rodrigues(rvec)
    
    sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
    singular = sy < 1e-6
    
    if not singular:
        x = np.arctan2(R[2,1], R[2,2])
        y = np.arctan2(-R[2,0], sy)
        z = np.arctan2(R[1,0], R[0,0])
    else:
        x = np.arctan2(-R[1,2], R[1,1])
        y = np.arctan2(-R[2,0], sy)
        z = 0
    
    return np.degrees(x), np.degrees(y), np.degrees(z)

def flip_z_axis(rvec, tvec):
    """Коррекция оси Z для AprilTag"""
    R, _ = cv2.Rodrigues(rvec)
    R_flip = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
    R_corrected = R @ R_flip
    rvec_corrected, _ = cv2.Rodrigues(R_corrected)
    return rvec_corrected, tvec

# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С КАМЕРОЙ
# ============================================================================

def init_camera():
    """Инициализация камеры"""
    global camera_matrix, dist_coeffs, width, height, cap, picam2
    
    print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
    print(f"{'='*50}")
    
    camera_matrix = np.load(CAMERA_MATRIX_FILE)
    dist_coeffs = np.load(DIST_COEFFS_FILE)
    
    if CAMERA_TYPE == 'usb':
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        picam2 = None
        print(f"✅ USB камера: {width}x{height}")
        
    else:  # CSI
        picam2 = Picamera2(0)
        config = picam2.create_video_configuration(
            main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": CAMERA_FPS, "AfMode": 2},
            buffer_count=4
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        
        width, height = CAMERA_WIDTH, CAMERA_HEIGHT
        cap = None
        print(f"✅ CSI камера: {width}x{height}")
    
    if width != CALIB_WIDTH:
        scale = width / CALIB_WIDTH
        camera_matrix[0,0] *= scale
        camera_matrix[1,1] *= scale
        camera_matrix[0,2] *= scale
        camera_matrix[1,2] *= scale
        print(f"✅ Матрица камеры отмасштабирована x{scale:.2f}")

def get_frame():
    """Получение кадра от камеры"""
    if CAMERA_TYPE == 'usb':
        ret, frame = cap.read()
        if not ret:
            return None
        return frame
    else:
        frame = picam2.capture_array()
        return frame

def resize_frame_to_display(frame, target_width, target_height):
    """Масштабирует кадр с сохранением пропорций"""
    h, w = frame.shape[:2]
    
    if h == 0 or w == 0 or target_width == 0 or target_height == 0:
        return frame, 1.0, 1.0, 0, 0, w, h
    
    aspect = w / h
    target_aspect = target_width / target_height
    
    if aspect > target_aspect:
        new_w = target_width
        new_h = int(target_width / aspect)
    else:
        new_h = target_height
        new_w = int(target_height * aspect)
    
    new_w = max(1, new_w)
    new_h = max(1, new_h)
    
    y_offset = (target_height - new_h) // 2
    x_offset = (target_width - new_w) // 2
    
    frame_resized = cv2.resize(frame, (new_w, new_h))
    
    display_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    display_frame[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized
    
    scale_x = new_w / w
    scale_y = new_h / h
    
    return display_frame, scale_x, scale_y, x_offset, y_offset, new_w, new_h

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    print(f"\n{'='*60}")
    print(f"🚀 APRILTAG 3D MODEL VIEWER (Два окна с точной настройкой)")
    print(f"{'='*60}")
    
    scale_x = 1.0
    scale_y = 1.0

    fullscreen_mode = False

    # Инициализация камеры
    init_camera()
    
    # Загрузка модели
    model = OBJModel(MODEL_PATH)
    
    # Инициализация AprilTag детектора
    print(f"\n🎯 ИНИЦИАЛИЗАЦИЯ APRILTAG")
    print(f"{'='*50}")
    detector = Detector(
        families=MARKER_FAMILY,
        nthreads=4,
        quad_decimate=1.0,
        quad_sigma=0.0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0
    )
    print(f"✅ Детектор инициализирован")
    print(f"   Целевой ID маркера: {TARGET_MARKER_ID}")
    
    # Загрузка конфигурации
    print(f"\n⚙️ ЗАГРУЗКА КОНФИГУРАЦИИ")
    print(f"{'='*50}")
    config = load_config(CONFIG_FILE)
    if config:
        slider_defaults = params_to_slider(config)
    else:
        slider_defaults = {
            'Scale_coarse': 50,
            'Scale_fine': 500,
            'Rot X_coarse': 180,
            'Rot Y_coarse': 180,
            'Rot Z_coarse': 180,
            'Rot X_fine': 500,
            'Rot Y_fine': 500,
            'Rot Z_fine': 500,
            'Offset X_coarse': 500,
            'Offset Y_coarse': 500,
            'Offset Z_coarse': 500,
            'Offset X_fine': 500,
            'Offset Y_fine': 500,
            'Offset Z_fine': 500,
            'Mode': 1
        }
    
    # ===== СОЗДАНИЕ ДВУХ ОКОН =====
    window_main = 'AprilTag Camera View'
    window_controls = 'Controls'
    
    # Главное окно с видео
    cv2.namedWindow(window_main, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_main, DISPLAY_WIDTH, DISPLAY_HEIGHT)
    cv2.moveWindow(window_main, 0, 0)
    
    # Окно с элементами управления
    cv2.namedWindow(window_controls, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_controls, 500, 700)  # Увеличил размер для двух групп слайдеров
    cv2.moveWindow(window_controls, DISPLAY_WIDTH - 500, 0)
    
    print(f"\n✅ Создано два окна:")
    print(f"   • {window_main} - {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    print(f"   • {window_controls} - 500x700 (с двумя группами слайдеров)")
    
    # Функция-заглушка для слайдеров
    def nothing(x):
        pass
    
    # Создание слайдеров в окне управления - ГРУБАЯ НАСТРОЙКА
    cv2.createTrackbar('Scale_coarse', window_controls, slider_defaults['Scale_coarse'], 100, nothing)
    cv2.createTrackbar('Rot X_coarse', window_controls, slider_defaults['Rot X_coarse'], 360, nothing)
    cv2.createTrackbar('Rot Y_coarse', window_controls, slider_defaults['Rot Y_coarse'], 360, nothing)
    cv2.createTrackbar('Rot Z_coarse', window_controls, slider_defaults['Rot Z_coarse'], 360, nothing)
    cv2.createTrackbar('Offset X_coarse', window_controls, slider_defaults['Offset X_coarse'], 1000, nothing)
    cv2.createTrackbar('Offset Y_coarse', window_controls, slider_defaults['Offset Y_coarse'], 1000, nothing)
    cv2.createTrackbar('Offset Z_coarse', window_controls, slider_defaults['Offset Z_coarse'], 1000, nothing)
    
    # Слайдеры для ТОЧНОЙ НАСТРОЙКИ
    cv2.createTrackbar('Scale_fine', window_controls, slider_defaults['Scale_fine'], 1000, nothing)
    cv2.createTrackbar('Rot X_fine', window_controls, slider_defaults['Rot X_fine'], 1000, nothing)
    cv2.createTrackbar('Rot Y_fine', window_controls, slider_defaults['Rot Y_fine'], 1000, nothing)
    cv2.createTrackbar('Rot Z_fine', window_controls, slider_defaults['Rot Z_fine'], 1000, nothing)
    cv2.createTrackbar('Offset X_fine', window_controls, slider_defaults['Offset X_fine'], 1000, nothing)
    cv2.createTrackbar('Offset Y_fine', window_controls, slider_defaults['Offset Y_fine'], 1000, nothing)
    cv2.createTrackbar('Offset Z_fine', window_controls, slider_defaults['Offset Z_fine'], 1000, nothing)
    
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_controls, slider_defaults['Mode'], 2, nothing)
    
    # Кнопки в главном окне
    button_width = 100
    button_height = 40
    margin = 10
    start_x = width - (button_width + margin) * 6

    buttons = [
        Button(start_x, 10, button_width, button_height, "SAVE", (50, 150, 50), (100, 255, 100)),
        Button(start_x + (button_width + margin) * 1, 10, button_width, button_height, "LOAD", (50, 50, 150), (100, 100, 255)),
        Button(start_x + (button_width + margin) * 2, 10, button_width, button_height, "RESET", (150, 150, 50), (255, 255, 100)),
        Button(start_x + (button_width + margin) * 3, 10, button_width, button_height, "ATTACH", (150, 50, 150), (255, 100, 255)),
        Button(start_x + (button_width + margin) * 4, 10, button_width, button_height, "FULL", (100, 100, 100), (150, 150, 150)),
        Button(start_x + (button_width + margin) * 5, 10, button_width, button_height, "EXIT", (150, 50, 50), (255, 100, 100))
    ]
    
    # Предвычисление ребер
    print(f"\n🔧 ПОДГОТОВКА ДАННЫХ")
    print(f"{'='*50}")
    edges = set()
    for face in model.faces:
        for i in range(len(face)):
            edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
            edges.add(edge)
    edges = list(edges)
    print(f"✅ Вычислено {len(edges)} ребер")
    
    # Переменные состояния
    marker_detected = False
    last_known_rvec = None
    last_known_tvec = None
    auto_center_requested = False
    
    # Для FPS
    last_time = time.time()
    frame_count = 0
    fps = 0
    
    print(f"\n{'='*60}")
    print(f"🚀 ЗАПУСК ОСНОВНОГО ЦИКЛА")
    print(f"{'='*60}")
    print(f"📸 Разрешение: {width}x{height}")
    print(f"🎯 Целевой маркер: ID {TARGET_MARKER_ID}")
    print(f"\n🖱️ Управление мышью в главном окне")
    print(f"🎚️ Слайдеры в окне Controls (две группы: coarse/fine)")
    print(f"\n{'='*60}\n")
    
    # Обработчик мыши для главного окна
    def mouse_callback(event, x, y, flags, param):
        nonlocal fullscreen_mode, auto_center_requested
        
        scale_x = param['scale_x']
        scale_y = param['scale_y']
        offset_x = param['offset_x']
        offset_y = param['offset_y']
        buttons = param['buttons']
        
        orig_x = int((x - offset_x) / scale_x)
        orig_y = int((y - offset_y) / scale_y)
        
        if orig_x < 0 or orig_y < 0 or orig_x >= width or orig_y >= height:
            return
        
        for button in buttons:
            button.is_hovered = button.is_inside(orig_x, orig_y)
        
        if event == cv2.EVENT_LBUTTONDOWN:
            for button in buttons:
                if button.is_inside(orig_x, orig_y):
                    if button.text == "SAVE":
                        slider_vals = {
                            'Scale_coarse': cv2.getTrackbarPos('Scale_coarse', window_controls),
                            'Scale_fine': cv2.getTrackbarPos('Scale_fine', window_controls),
                            'Rot X_coarse': cv2.getTrackbarPos('Rot X_coarse', window_controls),
                            'Rot Y_coarse': cv2.getTrackbarPos('Rot Y_coarse', window_controls),
                            'Rot Z_coarse': cv2.getTrackbarPos('Rot Z_coarse', window_controls),
                            'Rot X_fine': cv2.getTrackbarPos('Rot X_fine', window_controls),
                            'Rot Y_fine': cv2.getTrackbarPos('Rot Y_fine', window_controls),
                            'Rot Z_fine': cv2.getTrackbarPos('Rot Z_fine', window_controls),
                            'Offset X_coarse': cv2.getTrackbarPos('Offset X_coarse', window_controls),
                            'Offset Y_coarse': cv2.getTrackbarPos('Offset Y_coarse', window_controls),
                            'Offset Z_coarse': cv2.getTrackbarPos('Offset Z_coarse', window_controls),
                            'Offset X_fine': cv2.getTrackbarPos('Offset X_fine', window_controls),
                            'Offset Y_fine': cv2.getTrackbarPos('Offset Y_fine', window_controls),
                            'Offset Z_fine': cv2.getTrackbarPos('Offset Z_fine', window_controls),
                            'Mode': cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_controls)
                        }
                        params = slider_to_params(slider_vals)
                        save_config(CONFIG_FILE, params)
                        
                    elif button.text == "LOAD":
                        params = load_config(CONFIG_FILE)
                        if params:
                            slider_vals = params_to_slider(params)
                            cv2.setTrackbarPos('Scale_coarse', window_controls, slider_vals['Scale_coarse'])
                            cv2.setTrackbarPos('Scale_fine', window_controls, slider_vals['Scale_fine'])
                            cv2.setTrackbarPos('Rot X_coarse', window_controls, slider_vals['Rot X_coarse'])
                            cv2.setTrackbarPos('Rot Y_coarse', window_controls, slider_vals['Rot Y_coarse'])
                            cv2.setTrackbarPos('Rot Z_coarse', window_controls, slider_vals['Rot Z_coarse'])
                            cv2.setTrackbarPos('Rot X_fine', window_controls, slider_vals['Rot X_fine'])
                            cv2.setTrackbarPos('Rot Y_fine', window_controls, slider_vals['Rot Y_fine'])
                            cv2.setTrackbarPos('Rot Z_fine', window_controls, slider_vals['Rot Z_fine'])
                            cv2.setTrackbarPos('Offset X_coarse', window_controls, slider_vals['Offset X_coarse'])
                            cv2.setTrackbarPos('Offset Y_coarse', window_controls, slider_vals['Offset Y_coarse'])
                            cv2.setTrackbarPos('Offset Z_coarse', window_controls, slider_vals['Offset Z_coarse'])
                            cv2.setTrackbarPos('Offset X_fine', window_controls, slider_vals['Offset X_fine'])
                            cv2.setTrackbarPos('Offset Y_fine', window_controls, slider_vals['Offset Y_fine'])
                            cv2.setTrackbarPos('Offset Z_fine', window_controls, slider_vals['Offset Z_fine'])
                            cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_controls, slider_vals['Mode'])
                            
                    elif button.text == "RESET":
                        cv2.setTrackbarPos('Scale_coarse', window_controls, 50)
                        cv2.setTrackbarPos('Scale_fine', window_controls, 500)
                        cv2.setTrackbarPos('Rot X_coarse', window_controls, 180)
                        cv2.setTrackbarPos('Rot Y_coarse', window_controls, 180)
                        cv2.setTrackbarPos('Rot Z_coarse', window_controls, 180)
                        cv2.setTrackbarPos('Rot X_fine', window_controls, 500)
                        cv2.setTrackbarPos('Rot Y_fine', window_controls, 500)
                        cv2.setTrackbarPos('Rot Z_fine', window_controls, 500)
                        cv2.setTrackbarPos('Offset X_coarse', window_controls, 500)
                        cv2.setTrackbarPos('Offset Y_coarse', window_controls, 500)
                        cv2.setTrackbarPos('Offset Z_coarse', window_controls, 500)
                        cv2.setTrackbarPos('Offset X_fine', window_controls, 500)
                        cv2.setTrackbarPos('Offset Y_fine', window_controls, 500)
                        cv2.setTrackbarPos('Offset Z_fine', window_controls, 500)
                        print("\n🔄 Слайдеры сброшены")
                        
                    elif button.text == "ATTACH":
                        if marker_detected:
                            print("\n🔗 Привязка положения к маркеру...")
                            auto_center_requested = True
                        else:
                            print("\n⚠️ Маркер не обнаружен, привязка невозможна")
                            
                    elif button.text == "FULL":
                        fullscreen_mode = not fullscreen_mode
                        if fullscreen_mode:
                            print("\n🔍 Полноэкранный режим")
                            cv2.setWindowProperty(window_main, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                            # Минимизируем окно управления
                            cv2.resizeWindow(window_controls, 1, 1)
                            cv2.moveWindow(window_controls, -1000, -1000)
                        else:
                            print("\n🔍 Обычный режим")
                            cv2.setWindowProperty(window_main, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                            cv2.resizeWindow(window_main, DISPLAY_WIDTH, DISPLAY_HEIGHT)
                            cv2.moveWindow(window_main, 0, 0)
                            # Возвращаем окно управления
                            cv2.resizeWindow(window_controls, 500, 700)
                            cv2.moveWindow(window_controls, DISPLAY_WIDTH - 500, 0)

                    elif button.text == "EXIT":
                        print("\n👋 Выход...")
                        cv2.destroyAllWindows()
                        sys.exit(0)

    # Параметры для mouse callback
    mouse_param = {
        'buttons': buttons,
        'scale_x': 1.0,
        'scale_y': 1.0,
        'offset_x': 0,
        'offset_y': 0
    }
    
    cv2.setMouseCallback(window_main, mouse_callback, mouse_param)
    
    # Основной цикл
    try:
        while True:
            frame = get_frame()
            if frame is None:
                continue
            
            frame_count += 1
            if frame_count % 10 == 0:
                current_time = time.time()
                fps = 10 / (current_time - last_time)
                last_time = current_time
            
            # Детектирование AprilTag
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = detector.detect(
                gray,
                estimate_tag_pose=True,
                camera_params=[camera_matrix[0,0], camera_matrix[1,1], 
                             camera_matrix[0,2], camera_matrix[1,2]],
                tag_size=MARKER_SIZE / 1000.0
            )
            
            target_rvec = None
            target_tvec = None
            tag_info = "No tag detected"
            
            for detection in detections:
                corners = np.array(detection.corners, dtype=np.int32)
                color = (0, 255, 255) if detection.tag_id == TARGET_MARKER_ID else (0, 255, 0)
                cv2.polylines(frame, [corners], True, color, 3)
                
                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                rvec, tvec = flip_z_axis(rvec, tvec)
                
                if detection.tag_id == TARGET_MARKER_ID:
                    target_rvec = rvec
                    target_tvec = tvec
                    marker_detected = True
                    last_known_rvec = rvec.copy()
                    last_known_tvec = tvec.copy()
                    
                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.05)
                    
                    roll, pitch, yaw = rotation_vector_to_euler(rvec)
                    distance = np.linalg.norm(tvec)
                    tag_info = f"Tag ID:{detection.tag_id} | D:{distance:.2f}m | R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}"
                    
                    if auto_center_requested:
                        center_3d = np.array([[0, 0, 0]], dtype=np.float32)
                        center_2d, _ = cv2.projectPoints(center_3d, rvec, tvec, camera_matrix, dist_coeffs)
                        center_2d = center_2d[0][0]
                        
                        dx = width//2 - center_2d[0]
                        dy = height//2 - center_2d[1]
                        
                        print(f"   Смещение до центра: ({dx:.0f}, {dy:.0f}) пикселей")
                        auto_center_requested = False
            
            if target_rvec is None and last_known_rvec is not None:
                target_rvec = last_known_rvec
                target_tvec = last_known_tvec
                tag_info = "⚠️ USING LAST KNOWN POSITION"
            
            # Получаем значения слайдеров из окна управления
            slider_vals = {
                'Scale_coarse': cv2.getTrackbarPos('Scale_coarse', window_controls),
                'Scale_fine': cv2.getTrackbarPos('Scale_fine', window_controls),
                'Rot X_coarse': cv2.getTrackbarPos('Rot X_coarse', window_controls),
                'Rot Y_coarse': cv2.getTrackbarPos('Rot Y_coarse', window_controls),
                'Rot Z_coarse': cv2.getTrackbarPos('Rot Z_coarse', window_controls),
                'Rot X_fine': cv2.getTrackbarPos('Rot X_fine', window_controls),
                'Rot Y_fine': cv2.getTrackbarPos('Rot Y_fine', window_controls),
                'Rot Z_fine': cv2.getTrackbarPos('Rot Z_fine', window_controls),
                'Offset X_coarse': cv2.getTrackbarPos('Offset X_coarse', window_controls),
                'Offset Y_coarse': cv2.getTrackbarPos('Offset Y_coarse', window_controls),
                'Offset Z_coarse': cv2.getTrackbarPos('Offset Z_coarse', window_controls),
                'Offset X_fine': cv2.getTrackbarPos('Offset X_fine', window_controls),
                'Offset Y_fine': cv2.getTrackbarPos('Offset Y_fine', window_controls),
                'Offset Z_fine': cv2.getTrackbarPos('Offset Z_fine', window_controls),
                'Mode': cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_controls)
            }
            
            params = slider_to_params(slider_vals)
            
            # Отрисовка модели
            if target_rvec is not None:
                T_model_tag = model.get_transform_matrix(
                    params['scale'],
                    params['rot_x'], params['rot_y'], params['rot_z'],
                    params['offset_x'], params['offset_y'], params['offset_z']
                )
                
                R_tag, _ = cv2.Rodrigues(target_rvec)
                T_tag_cam = np.eye(4)
                T_tag_cam[:3, :3] = R_tag
                T_tag_cam[:3, 3] = target_tvec.flatten()
                
                T_model_cam = T_tag_cam @ T_model_tag
                
                transformed = model.transform(T_model_tag)
                img_points, _ = cv2.projectPoints(
                    transformed, 
                    target_rvec, target_tvec,
                    camera_matrix, dist_coeffs
                )
                img_points = np.int32(img_points).reshape(-1, 2)
                
                mode = params['mode']
                
                if mode == 0:
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 2, (0, 255, 255), -1)
                
                elif mode == 1:
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
                
                else:
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
            
            # Отрисовка кнопок в главном окне
            for button in buttons:
                button.draw(frame)
            
            # Информация на кадре
            info_lines = [
                f"FPS: {fps:.1f}",
                f"Target ID: {TARGET_MARKER_ID}",
                tag_info,
                f"Scale: {params['scale']:.6f}",
                f"Rot: {params['rot_x']:6.2f}° {params['rot_y']:6.2f}° {params['rot_z']:6.2f}°",
                f"Offset: X:{params['offset_x']:+.4f} Y:{params['offset_y']:+.4f} Z:{params['offset_z']:+.4f}m"
            ]
            
            y_offset = height - 180
            for line in info_lines:
                cv2.putText(frame, line, (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 20
            
            # Масштабируем кадр для главного окна
            display_frame, scale_x, scale_y, x_offset, y_offset, disp_w, disp_h = resize_frame_to_display(frame, DISPLAY_WIDTH, DISPLAY_HEIGHT)
            
            mouse_param['scale_x'] = scale_x
            mouse_param['scale_y'] = scale_y
            mouse_param['offset_x'] = x_offset
            mouse_param['offset_y'] = y_offset
            
            cv2.imshow(window_main, display_frame)
            
            # Создаем пустой кадр для окна управления с информацией
            controls_frame = np.zeros((700, 500, 3), dtype=np.uint8)
            
            # Заголовок
            cv2.putText(controls_frame, "CONTROL PANEL", (20, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Грубая настройка
            cv2.putText(controls_frame, "=== COARSE ADJUSTMENT ===", (20, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)
            
            # Точная настройка
            cv2.putText(controls_frame, "=== FINE ADJUSTMENT ===", (20, 300), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 200), 1)
            
            # Диапазоны точной настройки
            cv2.putText(controls_frame, "Scale: ±10%", (20, 320), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(controls_frame, "Rot: ±5 deg", (20, 340), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(controls_frame, "Offset: ±0.05m", (20, 360), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
            # Информация о маркере
            cv2.putText(controls_frame, f"Target ID: {TARGET_MARKER_ID}", (20, 400), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.putText(controls_frame, f"Detected: {'YES' if marker_detected else 'NO'}", (20, 420), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0) if marker_detected else (0, 0, 255), 1)
            
            # Текущие точные значения
            cv2.putText(controls_frame, f"Current fine values:", (20, 460), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(controls_frame, f"Scale fine: {(slider_vals['Scale_fine']-500)/500*10:+.1f}%", (20, 480), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(controls_frame, f"Rot fine: X{(slider_vals['Rot X_fine']-500)/100*5:+5.2f}° Y{(slider_vals['Rot Y_fine']-500)/100*5:+5.2f}° Z{(slider_vals['Rot Z_fine']-500)/100*5:+5.2f}°", (20, 500), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(controls_frame, f"Offset fine: X{(slider_vals['Offset X_fine']-500)/500*0.05:+6.3f} Y{(slider_vals['Offset Y_fine']-500)/500*0.05:+6.3f} Z{(slider_vals['Offset Z_fine']-500)/500*0.05:+6.3f}m", (20, 520), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
            cv2.imshow(window_controls, controls_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    
    except KeyboardInterrupt:
        print("\n👋 Прерывание пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n👋 Завершение работы...")
        if CAMERA_TYPE == 'usb' and cap:
            cap.release()
        elif picam2:
            picam2.stop()
        cv2.destroyAllWindows()
        print("✅ Программа завершена")

if __name__ == "__main__":
    main()