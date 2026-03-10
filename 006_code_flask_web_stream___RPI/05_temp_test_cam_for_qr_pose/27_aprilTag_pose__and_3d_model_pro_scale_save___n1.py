#!/usr/bin/env python3
"""
AprilTag 3D Model Viewer - Привязка 3D модели к AprilTag маркеру
Поддерживает USB и CSI камеры

Использование:
1. Запустите скрипт, модель появится в центре экрана
2. Используйте слайдеры для позиционирования модели
3. Нажмите "ATTACH TO TAG" чтобы привязать текущее положение к маркеру
4. Сохраните конфигурацию кнопкой "SAVE"

export DISPLAY=:0
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

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

# Тип камеры: 'usb' или 'csi'
CAMERA_TYPE = 'csi'

# Параметры камеры
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
TARGET_MARKER_ID = 3  # ID маркера для привязки

# Файлы модели и конфигурации
MODEL_PATH = "model_simple.obj"
CONFIG_FILE = "model_position.json"  # Базовое положение относительно маркера
ATTACH_CONFIG_FILE = "model_attached_position.json"  # Привязанное положение

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
                        # ПРЕДПОЛОЖЕНИЕ: вершины в миллиметрах, переводим в метры
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
        #print(f"{'='=60}\n")
        print(f"{'='*60}")
    
    def get_transform_matrix(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
        """
        Создает матрицу трансформации 4x4 из параметров
        Порядок: масштаб -> поворот -> смещение
        """
        # Матрица масштабирования
        S = np.diag([scale, scale, scale, 1.0])
        
        # Матрицы поворота
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
        
        # Общая матрица поворота (Z * Y * X)
        R = Rz @ Ry @ Rx
        
        # Матрица смещения
        T = np.eye(4)
        T[:3, 3] = [offset_x, offset_y, offset_z]
        
        # Итоговая матрица: T * R * S
        return T @ R @ S
    
    def transform(self, transform_matrix):
        """Применяет матрицу трансформации к вершинам"""
        if len(self.vertices) == 0:
            return None
        
        # Добавляем 1 для однородных координат
        vertices_h = np.hstack([self.vertices, np.ones((len(self.vertices), 1))])
        
        # Применяем трансформацию
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
        # Добавляем временную метку
        params_with_time = params.copy()
        params_with_time['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(config_file, 'w') as f:
            json.dump(params_with_time, f, indent=4)
        print(f"\n💾 Конфигурация сохранена в {config_file}")
        print(f"   Scale: {params.get('scale', 0):.3f}")
        print(f"   Rotation: ({params.get('rot_x', 0)}°, {params.get('rot_y', 0)}°, {params.get('rot_z', 0)}°)")
        print(f"   Offset: ({params.get('offset_x', 0):.3f}, {params.get('offset_y', 0):.3f}, {params.get('offset_z', 0):.3f})")
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
        print(f"   Время: {params.get('timestamp', 'unknown')}")
        print(f"   Scale: {params.get('scale', 0):.3f}")
        print(f"   Rotation: ({params.get('rot_x', 0)}°, {params.get('rot_y', 0)}°, {params.get('rot_z', 0)}°)")
        print(f"   Offset: ({params.get('offset_x', 0):.3f}, {params.get('offset_y', 0):.3f}, {params.get('offset_z', 0):.3f})")
        
        return params
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

def slider_to_params(slider_values):
    """Преобразование значений слайдеров в параметры"""
    params = {}
    
    # Scale: 0-100 -> 0.001-2.0 (логарифмическая шкала для точной настройки)
    if 'Scale' in slider_values:
        # log10(0.001) = -3, log10(2.0) = 0.301
        log_scale = -3 + (slider_values['Scale'] / 100) * 3.301
        params['scale'] = 10 ** log_scale
    
    # Rotations: 0-360 -> -180..180
    params['rot_x'] = slider_values.get('Rot X', 180) - 180
    params['rot_y'] = slider_values.get('Rot Y', 180) - 180
    params['rot_z'] = slider_values.get('Rot Z', 180) - 180
    
    # Offsets: 0-1000 -> -5..5 метров (для точной подстройки)
    params['offset_x'] = (slider_values.get('Offset X', 500) - 500) / 100.0
    params['offset_y'] = (slider_values.get('Offset Y', 500) - 500) / 100.0
    params['offset_z'] = (slider_values.get('Offset Z', 500) - 500) / 100.0
    
    # Mode
    params['mode'] = slider_values.get('Mode', 1)
    
    return params

def params_to_slider(params):
    """Преобразование параметров в значения слайдеров"""
    slider_values = {}
    
    # Scale: 0.001-2.0 -> 0-100
    if 'scale' in params:
        scale = max(0.001, min(2.0, params['scale']))
        log_scale = np.log10(scale)
        slider_values['Scale'] = int((log_scale + 3) * 100 / 3.301)
    
    # Rotations: -180..180 -> 0-360
    slider_values['Rot X'] = params.get('rot_x', 0) + 180
    slider_values['Rot Y'] = params.get('rot_y', 0) + 180
    slider_values['Rot Z'] = params.get('rot_z', 0) + 180
    
    # Offsets: -5..5 -> 0-1000
    slider_values['Offset X'] = int(params.get('offset_x', 0) * 100 + 500)
    slider_values['Offset Y'] = int(params.get('offset_y', 0) * 100 + 500)
    slider_values['Offset Z'] = int(params.get('offset_z', 0) * 100 + 500)
    
    slider_values['Mode'] = params.get('mode', 1)
    
    return slider_values

# ============================================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С APRILTAG
# ============================================================================

def rotation_vector_to_euler(rvec):
    """Преобразование вектора Родрига в углы Эйлера (градусы)"""
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
    """Инициализация камеры в зависимости от типа"""
    global camera_matrix, dist_coeffs, width, height, cap, picam2
    
    print(f"\n📹 ИНИЦИАЛИЗАЦИЯ КАМЕРЫ")
    print(f"{'='*50}")
    
    # Загружаем калибровку
    print(f"\n📷 Загрузка калибровки...")
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
    
    # Масштабируем матрицу камеры под текущее разрешение
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
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    else:
        frame = picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    print(f"\n{'='*60}")
    print(f"🚀 APRILTAG 3D MODEL VIEWER")
    print(f"{'='*60}")
    
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
    
    # Загрузка базовой конфигурации (положение относительно маркера)
    print(f"\n⚙️ ЗАГРУЗКА КОНФИГУРАЦИИ")
    print(f"{'='*50}")
    config = load_config(CONFIG_FILE)
    if config:
        slider_defaults = params_to_slider(config)
    else:
        # Значения по умолчанию (модель в центре, без смещения)
        slider_defaults = {
            'Scale': 50,  # ~0.1
            'Rot X': 180,
            'Rot Y': 180,
            'Rot Z': 180,
            'Offset X': 500,
            'Offset Y': 500,
            'Offset Z': 500,
            'Mode': 1
        }
    
    # Создание окна и слайдеров
    window_name = 'AprilTag 3D Model Viewer'
    cv2.namedWindow(window_name)
    
    # Функция-заглушка для слайдеров
    def nothing(x):
        pass
    
    # Создание слайдеров
    cv2.createTrackbar('Scale', window_name, slider_defaults['Scale'], 100, nothing)
    cv2.createTrackbar('Rot X', window_name, slider_defaults['Rot X'], 360, nothing)
    cv2.createTrackbar('Rot Y', window_name, slider_defaults['Rot Y'], 360, nothing)
    cv2.createTrackbar('Rot Z', window_name, slider_defaults['Rot Z'], 360, nothing)
    cv2.createTrackbar('Offset X', window_name, slider_defaults['Offset X'], 1000, nothing)
    cv2.createTrackbar('Offset Y', window_name, slider_defaults['Offset Y'], 1000, nothing)
    cv2.createTrackbar('Offset Z', window_name, slider_defaults['Offset Z'], 1000, nothing)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_name, slider_defaults['Mode'], 2, nothing)
    
    # Создание кнопок
    button_width = 100
    button_height = 40
    margin = 10
    start_x = width - (button_width + margin) * 5
    
    buttons = [
        Button(start_x, 10, button_width, button_height, "SAVE", (50, 150, 50), (100, 255, 100)),
        Button(start_x + button_width + margin, 10, button_width, button_height, "LOAD", (50, 50, 150), (100, 100, 255)),
        Button(start_x + (button_width + margin) * 2, 10, button_width, button_height, "RESET", (150, 150, 50), (255, 255, 100)),
        Button(start_x + (button_width + margin) * 3, 10, button_width, button_height, "ATTACH", (150, 50, 150), (255, 100, 255)),
        Button(start_x + (button_width + margin) * 4, 10, button_width, button_height, "EXIT", (150, 50, 50), (255, 100, 100))
    ]
    
    # Предвычисление ребер для отрисовки
    print(f"\n🔧 ПОДГОТОВКА ДАННЫХ")
    print(f"{'='*50}")
    edges = set()
    for face in model.faces:
        for i in range(len(face)):
            edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
            edges.add(edge)
    edges = list(edges)
    print(f"✅ Вычислено {len(edges)} ребер")
    
    # Переменные для отслеживания состояния
    marker_detected = False
    last_known_rvec = None
    last_known_tvec = None
    tag_position_text = "No tag detected"
    
    # Для FPS
    last_time = time.time()
    frame_count = 0
    fps = 0
    
    # Для автоцентрирования модели
    auto_center_requested = False
    
    print(f"\n{'='*60}")
    print(f"🚀 ЗАПУСК ОСНОВНОГО ЦИКЛА")
    print(f"{'='*60}")
    print(f"📸 Разрешение: {width}x{height}")
    print(f"🎯 Целевой маркер: ID {TARGET_MARKER_ID}")
    print(f"\n🖱️ Управление мышью:")
    print(f"   • SAVE - сохранить текущее положение")
    print(f"   • LOAD - загрузить сохраненное положение")
    print(f"   • RESET - сбросить слайдеры")
    print(f"   • ATTACH - привязать текущее положение к маркеру")
    print(f"   • EXIT - выход")
    print(f"\n🎚️ Слайдеры:")
    print(f"   • Scale - масштаб модели (логарифмическая шкала)")
    print(f"   • Rot X/Y/Z - поворот вокруг осей")
    print(f"   • Offset X/Y/Z - смещение относительно маркера")
    #print(f"\n{'='=60}\n")
    print(f"\n{'='*60}\n")
    # Обработчик мыши
    def mouse_callback(event, x, y, flags, param):
        nonlocal auto_center_requested
        
        # Обновляем состояние наведения для кнопок
        for button in buttons:
            button.is_hovered = button.is_inside(x, y)
        
        # Обработка кликов
        if event == cv2.EVENT_LBUTTONDOWN:
            for button in buttons:
                if button.is_inside(x, y):
                    if button.text == "SAVE":
                        # Сохраняем текущую конфигурацию
                        slider_vals = {
                            'Scale': cv2.getTrackbarPos('Scale', window_name),
                            'Rot X': cv2.getTrackbarPos('Rot X', window_name),
                            'Rot Y': cv2.getTrackbarPos('Rot Y', window_name),
                            'Rot Z': cv2.getTrackbarPos('Rot Z', window_name),
                            'Offset X': cv2.getTrackbarPos('Offset X', window_name),
                            'Offset Y': cv2.getTrackbarPos('Offset Y', window_name),
                            'Offset Z': cv2.getTrackbarPos('Offset Z', window_name),
                            'Mode': cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
                        }
                        params = slider_to_params(slider_vals)
                        save_config(CONFIG_FILE, params)
                        
                    elif button.text == "LOAD":
                        # Загружаем конфигурацию
                        params = load_config(CONFIG_FILE)
                        if params:
                            slider_vals = params_to_slider(params)
                            cv2.setTrackbarPos('Scale', window_name, slider_vals['Scale'])
                            cv2.setTrackbarPos('Rot X', window_name, slider_vals['Rot X'])
                            cv2.setTrackbarPos('Rot Y', window_name, slider_vals['Rot Y'])
                            cv2.setTrackbarPos('Rot Z', window_name, slider_vals['Rot Z'])
                            cv2.setTrackbarPos('Offset X', window_name, slider_vals['Offset X'])
                            cv2.setTrackbarPos('Offset Y', window_name, slider_vals['Offset Y'])
                            cv2.setTrackbarPos('Offset Z', window_name, slider_vals['Offset Z'])
                            cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_name, slider_vals['Mode'])
                            
                    elif button.text == "RESET":
                        # Сброс слайдеров
                        cv2.setTrackbarPos('Scale', window_name, 50)
                        cv2.setTrackbarPos('Rot X', window_name, 180)
                        cv2.setTrackbarPos('Rot Y', window_name, 180)
                        cv2.setTrackbarPos('Rot Z', window_name, 180)
                        cv2.setTrackbarPos('Offset X', window_name, 500)
                        cv2.setTrackbarPos('Offset Y', window_name, 500)
                        cv2.setTrackbarPos('Offset Z', window_name, 500)
                        print("\n🔄 Слайдеры сброшены")
                        
                    elif button.text == "ATTACH":
                        # Привязка текущего положения к маркеру
                        if marker_detected:
                            print("\n🔗 Привязка положения к маркеру...")
                            auto_center_requested = True
                        else:
                            print("\n⚠️ Маркер не обнаружен, привязка невозможна")
                            
                    elif button.text == "EXIT":
                        print("\n👋 Выход...")
                        cv2.destroyAllWindows()
                        sys.exit(0)
    
    cv2.setMouseCallback(window_name, mouse_callback)
    
    # Основной цикл
    try:
        while True:
            # Захват кадра
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
            
            # Поиск целевого маркера
            target_rvec = None
            target_tvec = None
            tag_info = "No tag detected"
            
            for detection in detections:
                # Рисуем контур маркера
                corners = np.array(detection.corners, dtype=np.int32)
                color = (0, 255, 255) if detection.tag_id == TARGET_MARKER_ID else (0, 255, 0)
                cv2.polylines(frame, [corners], True, color, 3)
                
                # Получаем позу
                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                rvec, tvec = flip_z_axis(rvec, tvec)
                
                # Если это целевой маркер
                if detection.tag_id == TARGET_MARKER_ID:
                    target_rvec = rvec
                    target_tvec = tvec
                    marker_detected = True
                    last_known_rvec = rvec.copy()
                    last_known_tvec = tvec.copy()
                    
                    # Рисуем оси маркера
                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.05)
                    
                    # Информация о маркере
                    roll, pitch, yaw = rotation_vector_to_euler(rvec)
                    distance = np.linalg.norm(tvec)
                    tag_info = f"Tag ID:{detection.tag_id} | D:{distance:.2f}m | R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}"
                    
                    # Автоцентрирование при запросе
                    if auto_center_requested:
                        # Вычисляем смещение от маркера до центра модели
                        #和目标: поместить модель в центр экрана
                        center_3d = np.array([[0, 0, 0]], dtype=np.float32)
                        center_2d, _ = cv2.projectPoints(center_3d, rvec, tvec, camera_matrix, dist_coeffs)
                        center_2d = center_2d[0][0]
                        
                        # Смещение до центра экрана
                        dx = width//2 - center_2d[0]
                        dy = height//2 - center_2d[1]
                        
                        print(f"   Смещение до центра: ({dx:.0f}, {dy:.0f}) пикселей")
                        print(f"   Для точной настройки используйте слайдеры Offset")
                        
                        auto_center_requested = False
            
            # Используем последнюю известную позицию если маркер пропал
            if target_rvec is None and last_known_rvec is not None:
                target_rvec = last_known_rvec
                target_tvec = last_known_tvec
                tag_info = "⚠️ USING LAST KNOWN POSITION"
            
            # Получаем значения слайдеров
            slider_vals = {
                'Scale': cv2.getTrackbarPos('Scale', window_name),
                'Rot X': cv2.getTrackbarPos('Rot X', window_name),
                'Rot Y': cv2.getTrackbarPos('Rot Y', window_name),
                'Rot Z': cv2.getTrackbarPos('Rot Z', window_name),
                'Offset X': cv2.getTrackbarPos('Offset X', window_name),
                'Offset Y': cv2.getTrackbarPos('Offset Y', window_name),
                'Offset Z': cv2.getTrackbarPos('Offset Z', window_name),
                'Mode': cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_name)
            }
            
            params = slider_to_params(slider_vals)
            
            # Если есть маркер, отрисовываем модель
            if target_rvec is not None:
                # Строим матрицу трансформации модели относительно маркера
                T_model_tag = model.get_transform_matrix(
                    params['scale'],
                    params['rot_x'], params['rot_y'], params['rot_z'],
                    params['offset_x'], params['offset_y'], params['offset_z']
                )
                
                # Матрица маркера относительно камеры
                R_tag, _ = cv2.Rodrigues(target_rvec)
                T_tag_cam = np.eye(4)
                T_tag_cam[:3, :3] = R_tag
                T_tag_cam[:3, 3] = target_tvec.flatten()
                
                # Итоговая матрица: модель в системе камеры
                T_model_cam = T_tag_cam @ T_model_tag
                
                # Извлекаем rvec и tvec для projectPoints
                rvec_total, _ = cv2.Rodrigues(T_model_cam[:3, :3])
                tvec_total = T_model_cam[:3, 3].reshape(3, 1)
                
                # Трансформируем и проецируем вершины
                transformed = model.transform(T_model_tag)  # Модель в системе маркера
                img_points, _ = cv2.projectPoints(
                    transformed, 
                    target_rvec, target_tvec,  # Используем маркер как базовый
                    camera_matrix, dist_coeffs
                )
                img_points = np.int32(img_points).reshape(-1, 2)
                
                # Отрисовка модели
                mode = params['mode']
                
                if mode == 0:  # Точки
                    for pt in img_points:
                        if 0 <= pt[0] < width and 0 <= pt[1] < height:
                            cv2.circle(frame, tuple(pt), 2, (0, 255, 255), -1)
                
                elif mode == 1:  # Каркас
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
                
                else:  # Грани
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
            
            # Отрисовка кнопок
            for button in buttons:
                button.draw(frame)
            
            # Отрисовка информации
            info_lines = [
                f"FPS: {fps:.1f}",
                f"Target ID: {TARGET_MARKER_ID}",
                tag_info,
                f"Scale: {params['scale']:.4f}",
                f"Rot: {params['rot_x']:3d}° {params['rot_y']:3d}° {params['rot_z']:3d}°",
                f"Offset: X:{params['offset_x']:+.2f} Y:{params['offset_y']:+.2f} Z:{params['offset_z']:+.2f}m"
            ]
            
            y_offset = height - 180
            for line in info_lines:
                cv2.putText(frame, line, (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 20
            
            # Показываем кадр
            cv2.imshow(window_name, frame)
            
            # Обработка клавиш (запасной вариант)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # q или ESC
                break
    
    except KeyboardInterrupt:
        print("\n👋 Прерывание пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Очистка
        print("\n👋 Завершение работы...")
        if CAMERA_TYPE == 'usb' and cap:
            cap.release()
        elif picam2:
            picam2.stop()
        cv2.destroyAllWindows()
        print("✅ Программа завершена")

if __name__ == "__main__":
    main()