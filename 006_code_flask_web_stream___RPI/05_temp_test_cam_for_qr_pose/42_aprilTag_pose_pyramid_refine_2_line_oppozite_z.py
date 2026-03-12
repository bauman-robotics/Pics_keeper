#!/usr/bin/env python3
"""
AprilTag 3D Model Viewer - Привязка 3D модели к AprilTag маркеру
Поддерживает USB и CSI камеры
Версия с двумя окнами: видео и управление
+ Уточнение позы по пересекающимся линиям на гранях усечённой пирамиды


1. убить сессию:
screen -X -S bird_detector quit

export DISPLAY=:0

source /home/pi/projects/Hailo8_projects/Pics_keeper/venv/bin/activate
cd /home/pi/projects/Hailo8_projects/Pics_keeper/006_code_flask_web_stream___RPI/
python3 42_aprilTag_pose_pyramid_refine_2_line_oppozite_z.py

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
try:
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    DISPLAY_SCALE = 0.95
    DISPLAY_WIDTH = int(screen_width * DISPLAY_SCALE)
    DISPLAY_HEIGHT = int(screen_height * DISPLAY_SCALE)
    print(f"\n🖥️ SCREEN RESOLUTION")
    print(f"{'='*50}")
    print(f"   Screen: {screen_width}x{screen_height}")
    print(f"   Window: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT} ({DISPLAY_SCALE*100:.0f}%)")
except:
    DISPLAY_WIDTH = 1280
    DISPLAY_HEIGHT = 720
    print(f"\n⚠️ Could not detect screen size, using {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")

# ============================================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# ============================================================================

CAMERA_TYPE = 'csi'
CAMERA_WIDTH = 1536
CAMERA_HEIGHT = 864
CAMERA_FPS = 30

CALIB_WIDTH = 640
CALIB_HEIGHT = 480
CALIB_PATH = '04_cam_imx708_calibration_results'
CAMERA_MATRIX_FILE = f'{CALIB_PATH}/camera_matrix_imx708.npy'
DIST_COEFFS_FILE = f'{CALIB_PATH}/dist_coeffs_imx708.npy'

MARKER_SIZE = 20        # мм, размер AprilTag для PnP (внешний)
MARKER_FAMILY = 'tag36h11'
TARGET_MARKER_ID = 3

MODEL_PATH = "model_simple.obj"
CONFIG_FILE = "model_position.json"

# ============================================================================
# ПАРАМЕТРЫ УСЕЧЁННОЙ ПИРАМИДЫ (настраиваемые)
# ============================================================================

PYRAMID_BASE_SIZE   = 40.0   # мм, сторона нижнего основания квадрата
PYRAMID_TOP_SIZE    = 24.0   # мм, сторона верхней грани (где AprilTag)
PYRAMID_ANGLE_DEG   = 45.0   # градусов, угол боковой грани к горизонтали
LINE_WIDTH          = 2.0    # мм, толщина пересекающихся линий на гранях

# Порог репроекционной ошибки для принятия найденной точки (пиксели)
PYRAMID_REPROJ_THRESHOLD = 25.0

# Запас ROI относительно проецированного размера паттерна (множитель)
PYRAMID_ROI_MARGIN = 4.0

# ============================================================================
# ОТЛАДКА
# ============================================================================

# Установить True для вывода промежуточных расчётов координат
# центров пересечения линий в консольный лог
DEBUG_PYRAMID = False

WINDOWS_CONTROL_EN = False 

# ============================================================================
# ВЫЧИСЛЕНИЕ ГЕОМЕТРИИ ПИРАМИДЫ (один раз при старте)
# ============================================================================

def compute_pyramid_geometry():
    """
    Вычисляет 3D координаты центров боковых граней пирамиды
    в системе координат AprilTag (начало = центр верхней грани, Z вниз).
    
    Возвращает:
        faces: list of dict с ключами:
            'name'      - название грани
            'center_3d' - np.array([x, y, z]) в мм
            'normal'    - np.array([nx, ny, nz]) единичная нормаль (наружу)
    """
    angle_rad = np.radians(PYRAMID_ANGLE_DEG)
    top  = PYRAMID_TOP_SIZE  / 2.0   # полуразмер верхней грани
    base = PYRAMID_BASE_SIZE / 2.0   # полуразмер нижней грани

    # Высота пирамиды из угла граней
    h = (base - top) * np.tan(angle_rad)

    if DEBUG_PYRAMID:
        print(f"\n[PYRAMID GEOMETRY]")
        print(f"  top={top*2:.1f}mm, base={base*2:.1f}mm, angle={PYRAMID_ANGLE_DEG}°, h={h:.2f}mm")

    # В системе AprilTag: Z положительное идет ВНИЗ (вглубь от маркера)
    # Но для визуализации нам нужно, чтобы пирамида была ПОД маркером
    # Поэтому используем отрицательный Z для нижней части
    h_display = -h  # Отрицательное значение для отображения под маркером

    # Вершины каждой трапециевидной грани (по часовой стрелке глядя снаружи)
    # Система координат: X вправо, Y вниз (вглубь по Y), Z вниз (высота)
    # Верхняя грань Z=0, нижнее основание Z=+h (в системе AprilTag)
    # Но для отображения используем Z=-h (под маркером)

    faces_vertices = {
        'FRONT': [  # нормаль смотрит в -Y
            np.array([-top,  -top,  0.0]),
            np.array([ top,  -top,  0.0]),
            np.array([ base, -base,  h_display]),  # Отрицательный Z!
            np.array([-base, -base,  h_display]),  # Отрицательный Z!
        ],
        'BACK': [   # нормаль смотрит в +Y
            np.array([ top,   top,  0.0]),
            np.array([-top,   top,  0.0]),
            np.array([-base,  base,  h_display]),  # Отрицательный Z!
            np.array([ base,  base,  h_display]),  # Отрицательный Z!
        ],
        'LEFT': [   # нормаль смотрит в -X
            np.array([-top,  -top,  0.0]),
            np.array([-top,   top,  0.0]),
            np.array([-base,  base,  h_display]),  # Отрицательный Z!
            np.array([-base, -base,  h_display]),  # Отрицательный Z!
        ],
        'RIGHT': [  # нормаль смотрит в +X
            np.array([top,    top,  0.0]),
            np.array([top,   -top,  0.0]),
            np.array([base,  -base,  h_display]),  # Отрицательный Z!
            np.array([base,   base,  h_display]),  # Отрицательный Z!
        ],
    }

    # Наружные нормали граней (в локальной системе координат, до поворота камерой)
    face_normals = {
        'FRONT': np.array([ 0.0, -1.0,  0.0]),
        'BACK':  np.array([ 0.0,  1.0,  0.0]),
        'LEFT':  np.array([-1.0,  0.0,  0.0]),
        'RIGHT': np.array([ 1.0,  0.0,  0.0]),
    }
    
    # Наклон нормали с учётом угла грани
    sin_a = np.sin(angle_rad)
    cos_a = np.cos(angle_rad)
    
    # Нормали тоже нужно скорректировать для отрицательного Z
    face_normals_tilted = {
        'FRONT': np.array([ 0.0,  -cos_a,  sin_a]),  # Знак Z изменен!
        'BACK':  np.array([ 0.0,   cos_a,  sin_a]),  # Знак Z изменен!
        'LEFT':  np.array([-cos_a, 0.0,    sin_a]),  # Знак Z изменен!
        'RIGHT': np.array([ cos_a, 0.0,    sin_a]),  # Знак Z изменен!
    }

    faces = []
    for name, verts in faces_vertices.items():
        # Центр грани = среднее 4 вершин
        center = np.mean(verts, axis=0).astype(np.float32)
        normal = face_normals_tilted[name].astype(np.float32)
        normal /= np.linalg.norm(normal)  # нормализация

        faces.append({
            'name':      name,
            'center_3d': center,        # мм, в системе AprilTag (с отрицательным Z)
            'normal':    normal,
        })

        if DEBUG_PYRAMID:
            print(f"  Face {name}: center_3d={center} mm, normal={normal}")

    return faces, h  # Возвращаем положительную высоту для других расчетов


# Предвычисляем геометрию один раз при загрузке модуля
PYRAMID_FACES, PYRAMID_HEIGHT = compute_pyramid_geometry()


# ============================================================================
# ДЕТЕКТИРОВАНИЕ ТОЧЕК ПЕРЕСЕЧЕНИЯ ЛИНИЙ НА ГРАНЯХ ПИРАМИДЫ
# ============================================================================

def is_face_visible(face_normal_local, rvec, tvec):
    """
    Проверяет видима ли грань камерой.
    Грань видима если нормаль (в мировой СК) имеет компоненту направленную к камере.

    face_normal_local: np.array(3,) нормаль в системе координат маркера
    rvec, tvec: поза маркера
    Возвращает: (bool, float) - (видима, значение dot product)
    """
    R, _ = cv2.Rodrigues(rvec)
    # Нормаль грани в системе координат камеры
    normal_cam = R @ face_normal_local
    # Вектор от центра маркера к камере (в СК камеры = -tvec направление)
    # В СК камеры камера в начале координат, маркер в tvec
    # Вектор "от маркера к камере" в СК камеры = -tvec / ||tvec||
    vec_to_cam = -tvec.flatten() / (np.linalg.norm(tvec) + 1e-9)
    dot = float(np.dot(normal_cam, vec_to_cam))
    return dot > 0.0, dot


def compute_roi_size(pattern_size_mm, distance_m, fx):
    """
    Вычисляет размер ROI в пикселях для поиска точки пересечения линий.
    pattern_size_mm: физический размер паттерна (размер грани)
    distance_m: расстояние до маркера в метрах
    fx: фокусное расстояние камеры в пикселях
    """
    if distance_m < 0.01:
        distance_m = 0.01
    pattern_size_m = pattern_size_mm / 1000.0
    projected_px = (pattern_size_m * fx) / distance_m
    roi_size = int(projected_px * PYRAMID_ROI_MARGIN)
    roi_size = max(roi_size, 40)   # минимум 40px
    roi_size = min(roi_size, 300)  # максимум 300px
    return roi_size

def detect_pyramid_corners(frame_gray, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Детектирует точки пересечения линий на боковых гранях пирамиды.
    С правильным определением направления вертикальной оси.
    """
    results = []
    h, w = frame_gray.shape[:2]
    distance_m = float(np.linalg.norm(tvec))
    fx = camera_matrix[0, 0]

    # Матрица поворота
    R, _ = cv2.Rodrigues(rvec)

    for face in PYRAMID_FACES:
        name = face['name']
        center_3d = face['center_3d']
        normal = face['normal']

        visible, dot_val = is_face_visible(normal, rvec, tvec)

        # Проецируем центр грани
        center_m = (center_3d / 1000.0).reshape(1, 1, 3).astype(np.float32)
        proj, _ = cv2.projectPoints(center_m, rvec, tvec, camera_matrix, dist_coeffs)
        px, py = proj[0][0]

        result_base = {
            'face': name,
            'center_3d': center_3d,
            'corner_2d': None,
            'proj_2d': np.array([px, py]),
            'reproj_err': None,
            'visible': visible,
            'confidence': 0.0,
        }

        if not visible:
            results.append(result_base)
            continue

        # ========== ПРОЕЦИРУЕМ ВСЕ 4 УГЛА ГРАНИ ==========
        half_top = PYRAMID_TOP_SIZE / 2.0 / 1000.0  # в метрах
        half_base = PYRAMID_BASE_SIZE / 2.0 / 1000.0
        h_pyr = PYRAMID_HEIGHT / 1000.0
        
        if name == 'FRONT':
            vertices_3d = np.array([
                [-half_top, -half_top, 0.0],
                [ half_top, -half_top, 0.0],
                [ half_base, -half_base, h_pyr],
                [-half_base, -half_base, h_pyr]
            ], dtype=np.float32)
        elif name == 'BACK':
            vertices_3d = np.array([
                [ half_top, half_top, 0.0],
                [-half_top, half_top, 0.0],
                [-half_base, half_base, h_pyr],
                [ half_base, half_base, h_pyr]
            ], dtype=np.float32)
        elif name == 'LEFT':
            vertices_3d = np.array([
                [-half_top, -half_top, 0.0],
                [-half_top, half_top, 0.0],
                [-half_base, half_base, h_pyr],
                [-half_base, -half_base, h_pyr]
            ], dtype=np.float32)
        else:  # RIGHT
            vertices_3d = np.array([
                [ half_top, half_top, 0.0],
                [ half_top, -half_top, 0.0],
                [ half_base, -half_base, h_pyr],
                [ half_base, half_base, h_pyr]
            ], dtype=np.float32)
        
        # Проецируем углы
        vertices_2d, _ = cv2.projectPoints(
            vertices_3d, rvec, tvec, camera_matrix, dist_coeffs
        )
        vertices_2d = vertices_2d.reshape(-1, 2)
        
        # Bounding box грани
        min_x = np.min(vertices_2d[:, 0])
        max_x = np.max(vertices_2d[:, 0])
        min_y = np.min(vertices_2d[:, 1])
        max_y = np.max(vertices_2d[:, 1])
        
        face_width = max_x - min_x
        face_height = max_y - min_y
        margin_x = face_width * 0.3
        margin_y = face_height * 0.3
        
        x1 = max(int(min_x - margin_x), 0)
        y1 = max(int(min_y - margin_y), 0)
        x2 = min(int(max_x + margin_x), w)
        y2 = min(int(max_y + margin_y), h)
        
        if (x2 - x1) < 40 or (y2 - y1) < 40:
            results.append(result_base)
            continue
        
        roi = frame_gray[y1:y2, x1:x2]
        
        # ========== ОПРЕДЕЛЕНИЕ НАПРАВЛЕНИЙ ЛИНИЙ ==========
        
        # Базовая ориентация в 3D (в системе координат маркера)
        if name == 'FRONT' or name == 'BACK':
            # Для FRONT/BACK: горизонталь вдоль X, вертикаль вдоль Z
            horizontal_dir_3d = np.array([1.0, 0.0, 0.0])
            vertical_dir_3d = np.array([0.0, 0.0, 1.0])
            
            # Точки для проверки вертикального направления
            top_point_3d = center_3d / 1000.0  # верх грани (Z=0)
            bottom_point_3d = center_3d / 1000.0 + np.array([0.0, 0.0, h_pyr])  # низ грани (Z=h_pyr)
        else:  # LEFT или RIGHT
            # Для LEFT/RIGHT: горизонталь вдоль Y, вертикаль вдоль Z
            horizontal_dir_3d = np.array([0.0, 1.0, 0.0])
            vertical_dir_3d = np.array([0.0, 0.0, 1.0])
            
            top_point_3d = center_3d / 1000.0
            bottom_point_3d = center_3d / 1000.0 + np.array([0.0, 0.0, h_pyr])
        
        # Проецируем верхнюю и нижнюю точки для определения направления вертикали
        top_point_2d, _ = cv2.projectPoints(
            np.array([top_point_3d], dtype=np.float32), 
            rvec, tvec, camera_matrix, dist_coeffs
        )
        bottom_point_2d, _ = cv2.projectPoints(
            np.array([bottom_point_3d], dtype=np.float32), 
            rvec, tvec, camera_matrix, dist_coeffs
        )
        
        top_point_2d = top_point_2d[0][0]
        bottom_point_2d = bottom_point_2d[0][0]
        
        # Вектор вертикали на изображении
        vertical_dir_2d_observed = bottom_point_2d - top_point_2d
        
        # Нормализуем
        vertical_dir_2d_observed = vertical_dir_2d_observed / np.linalg.norm(vertical_dir_2d_observed)
        
        if DEBUG_PYRAMID:
            print(f"  Face {name}: vertical direction = ({vertical_dir_2d_observed[0]:.2f}, {vertical_dir_2d_observed[1]:.2f})")
        
        # ========== ПОИСК ЛИНИЙ С ПРАВИЛЬНЫМИ НАПРАВЛЕНИЯМИ ==========
        
        # Предобработка
        roi_blur = cv2.GaussianBlur(roi, (5, 5), 0)
        edges = cv2.Canny(roi_blur, 50, 150, apertureSize=3)
        
        # Поиск линий через преобразование Хафа
        lines = cv2.HoughLinesP(
            edges, 
            rho=1, 
            theta=np.pi/180, 
            threshold=30,
            minLineLength=roi.shape[1] // 4,
            maxLineGap=10
        )
        
        if lines is None or len(lines) < 4:
            if DEBUG_PYRAMID:
                print(f"  Face {name}: not enough lines found")
            results.append(result_base)
            continue
        
        # Классифицируем линии
        lines_list = lines[:, 0, :]
        
        # Для каждой линии вычисляем направление и центр
        horizontal_candidates = []
        vertical_candidates = []
        
        for line in lines_list:
            x1_l, y1_l, x2_l, y2_l = line
            
            # Направление линии
            dx = x2_l - x1_l
            dy = y2_l - y1_l
            length = np.sqrt(dx*dx + dy*dy)
            
            if length < 10:
                continue
                
            dir_vec = np.array([dx, dy]) / length
            
            # Центр линии
            center_x = (x1_l + x2_l) / 2
            center_y = (y1_l + y2_l) / 2
            
            # Проверяем, насколько линия соответствует ожидаемым направлениям
            
            # Для горизонтали: сравниваем с горизонтальным направлением в 3D
            # Горизонтальное направление в 2D - перпендикулярно вертикали
            horizontal_dir_2d = np.array([-vertical_dir_2d_observed[1], vertical_dir_2d_observed[0]])
            
            # Вычисляем сходство с горизонталью (скалярное произведение)
            h_similarity = abs(np.dot(dir_vec, horizontal_dir_2d))
            
            # Вычисляем сходство с вертикалью
            v_similarity = abs(np.dot(dir_vec, vertical_dir_2d_observed))
            
            # Классифицируем
            if h_similarity > 0.7:  # порог для горизонтали
                horizontal_candidates.append({
                    'line': line,
                    'center': (center_x, center_y),
                    'similarity': h_similarity
                })
            elif v_similarity > 0.7:  # порог для вертикали
                vertical_candidates.append({
                    'line': line,
                    'center': (center_x, center_y),
                    'similarity': v_similarity
                })
        
        if len(horizontal_candidates) == 0 or len(vertical_candidates) == 0:
            if DEBUG_PYRAMID:
                print(f"  Face {name}: missing line orientations (h={len(horizontal_candidates)}, v={len(vertical_candidates)})")
            results.append(result_base)
            continue
        
        # Выбираем лучшие линии (ближайшие к центру ROI)
        roi_center_x = roi.shape[1] / 2
        roi_center_y = roi.shape[0] / 2
        
        # Для горизонтальных линий: сортируем по расстоянию до центра по Y
        horizontal_candidates.sort(key=lambda c: abs(c['center'][1] - roi_center_y))
        # Для вертикальных линий: сортируем по расстоянию до центра по X
        vertical_candidates.sort(key=lambda c: abs(c['center'][0] - roi_center_x))
        
        best_horizontal = horizontal_candidates[0]['line']
        best_vertical = vertical_candidates[0]['line']
        
        # Находим пересечение
        # Находим пересечение двух линий
        x1_h, y1_h, x2_h, y2_h = best_horizontal
        x1_v, y1_v, x2_v, y2_v = best_vertical

        # Параметры линий
        a_h = y2_h - y1_h
        b_h = x1_h - x2_h
        c_h = x2_h * y1_h - x1_h * y2_h

        a_v = y2_v - y1_v
        b_v = x1_v - x2_v
        c_v = x2_v * y1_v - x1_v * y2_v

        det = a_h * b_v - a_v * b_h
        if abs(det) < 1e-6:
            if DEBUG_PYRAMID:
                print(f"  Face {name}: lines are parallel")
            results.append(result_base)
            continue

        # Точка пересечения в ROI
        cx_roi = (b_h * c_v - b_v * c_h) / det
        cy_roi = (c_h * a_v - c_v * a_h) / det

        # ========== ВАЖНО: ПРОВЕРКА ГРАНИЦ ==========
        # Проверяем, что точка внутри ROI с запасом
        margin = 5  # пикселей отступа
        roi_h, roi_w = roi.shape[:2]

        if (cx_roi < margin or cx_roi >= roi_w - margin or 
            cy_roi < margin or cy_roi >= roi_h - margin):
            if DEBUG_PYRAMID:
                print(f"  Face {name}: intersection near boundary ({cx_roi:.1f}, {cy_roi:.1f}) in ROI {roi_w}x{roi_h}")
            
            # Пробуем скорректировать точку, если она недалеко за границей
            cx_roi = np.clip(cx_roi, margin, roi_w - margin - 1)
            cy_roi = np.clip(cy_roi, margin, roi_h - margin - 1)
            
            # Проверяем снова после клиппинга
            if cx_roi < margin or cx_roi >= roi_w - margin:
                results.append(result_base)
                continue

        # Субпиксельное уточнение с проверкой
        try:
            candidate = np.array([[[cx_roi, cy_roi]]], dtype=np.float32)
            
            # Дополнительная проверка для cornerSubPix
            if (cx_roi < 0 or cx_roi >= roi_w or 
                cy_roi < 0 or cy_roi >= roi_h):
                if DEBUG_PYRAMID:
                    print(f"  Face {name}: candidate out of bounds")
                results.append(result_base)
                continue
            
            corners_subpix = cv2.cornerSubPix(
                roi,
                candidate,
                winSize=(11, 11),  # Уменьшаем размер окна для большей надежности
                zeroZone=(-1, -1),
                criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            )
            
            corner_roi = corners_subpix[0][0]
            
            # Проверяем результат субпиксельного уточнения
            if (corner_roi[0] < 0 or corner_roi[0] >= roi_w or 
                corner_roi[1] < 0 or corner_roi[1] >= roi_h):
                if DEBUG_PYRAMID:
                    print(f"  Face {name}: subpix result out of bounds")
                results.append(result_base)
                continue
                
        except cv2.error as e:
            if DEBUG_PYRAMID:
                print(f"  Face {name}: cornerSubPix error: {e}")
            results.append(result_base)
            continue
        
        # Субпиксельное уточнение
        candidate = np.array([[[cx_roi, cy_roi]]], dtype=np.float32)
        corners_subpix = cv2.cornerSubPix(
            roi,
            candidate,
            winSize=(11, 11),
            zeroZone=(-1, -1),
            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        )
        
        corner_roi = corners_subpix[0][0]
        corner_full = np.array(
            [corner_roi[0] + x1, corner_roi[1] + y1],
            dtype=np.float32
        )
        
        # Репроекционная ошибка
        reproj_err = float(np.linalg.norm(corner_full - np.array([px, py])))
        
        if reproj_err > PYRAMID_REPROJ_THRESHOLD * (1.0 + distance_m):
            if DEBUG_PYRAMID:
                print(f"  Face {name}: reproj_err={reproj_err:.1f}px")
            results.append(result_base)
            continue
        
        # Уверенность
        confidence = min(1.0, 
                        (len(horizontal_candidates) + len(vertical_candidates)) / 10.0 *
                        (1.0 - reproj_err / (PYRAMID_REPROJ_THRESHOLD * 2)))
        
        result = result_base.copy()
        result['corner_2d'] = corner_full
        result['reproj_err'] = reproj_err
        result['confidence'] = max(0.3, confidence)
        
        if DEBUG_PYRAMID:
            print(f"  Face {name}: FOUND at ({corner_full[0]:.1f},{corner_full[1]:.1f}), "
                  f"conf={confidence:.2f}")
        
        results.append(result)
    
    return results
    
# ============================================================================
# УТОЧНЕНИЕ ПОЗЫ С ДОПОЛНИТЕЛЬНЫМИ ТОЧКАМИ
# ============================================================================

def refine_pose_with_pyramid_corners(
        rvec_init, tvec_init,
        apriltag_obj_pts, apriltag_img_pts,
        pyramid_results,
        camera_matrix, dist_coeffs):
    """
    Уточняет позу маркера используя точки AprilTag + найденные точки пересечения линий.
    Улучшенная версия с взвешиванием точек по уверенности и RANSAC.
    
    Returns:
        rvec_refined, tvec_refined, n_extra_points, reproj_before, reproj_after
    """
    # Собираем дополнительные точки с весами
    extra_obj = []
    extra_img = []
    weights = []  # Веса для точек (можно использовать в будущем)
    
    for r in pyramid_results:
        # Используем только точки с высокой уверенностью, если доступно
        confidence = r.get('confidence', 1.0) if isinstance(r, dict) else 1.0
        if r['corner_2d'] is not None and confidence > 0.3:  # Порог уверенности
            extra_obj.append(r['center_3d'] / 1000.0)  # мм → метры
            extra_img.append(r['corner_2d'])
            weights.append(confidence)

    n_extra = len(extra_obj)

    # Если нет дополнительных точек или их слишком мало — возвращаем исходную позу
    if n_extra < 2:  # Нужно минимум 2 точки для стабильности
        if DEBUG_PYRAMID:
            print(f"  [REFINE] Not enough extra points ({n_extra}), using original pose")
        return rvec_init, tvec_init, 0, None, None

    # Формируем объединённый набор точек
    # AprilTag точки: мм → метры
    obj_pts_combined = np.vstack([
        apriltag_obj_pts / 1000.0,
        np.array(extra_obj, dtype=np.float32)
    ]).astype(np.float32)

    img_pts_tag = apriltag_img_pts.reshape(-1, 1, 2).astype(np.float32)
    img_pts_extra = np.array(extra_img, dtype=np.float32).reshape(-1, 1, 2)
    img_pts_combined = np.vstack([img_pts_tag, img_pts_extra])

    # Репроекционная ошибка ДО уточнения
    proj_before, _ = cv2.projectPoints(
        obj_pts_combined, rvec_init, tvec_init, camera_matrix, dist_coeffs
    )
    errors_before = np.linalg.norm(
        proj_before.reshape(-1, 2) - img_pts_combined.reshape(-1, 2), axis=1
    )
    reproj_before = float(np.mean(errors_before))
    
    # Дополнительно: медианная ошибка (более робастная)
    median_error_before = float(np.median(errors_before))

    if DEBUG_PYRAMID:
        print(f"  [REFINE] Before: mean={reproj_before:.2f}px, median={median_error_before:.2f}px")

    # Уточнение PnP
    try:
        # Пробуем RANSAC для устойчивости к выбросам
        ret, rvec_ref, tvec_ref, inliers = cv2.solvePnPRansac(
            obj_pts_combined,
            img_pts_combined,
            camera_matrix,
            dist_coeffs,
            useExtrinsicGuess=True,
            rvec=rvec_init.copy(),
            tvec=tvec_init.copy(),
            iterationsCount=500,           # Больше итераций
            reprojectionError=10.0,        # Порог ошибки в пикселях
            confidence=0.99,                # Высокая уверенность
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        # Если RANSAC не сработал, пробуем обычный PnP
        if not ret or inliers is None or len(inliers) < 4:
            if DEBUG_PYRAMID:
                print(f"  [REFINE] RANSAC failed ({len(inliers) if inliers is not None else 0} inliers), trying standard PnP")
            
            ret, rvec_ref, tvec_ref = cv2.solvePnP(
                obj_pts_combined,
                img_pts_combined,
                camera_matrix,
                dist_coeffs,
                rvec=rvec_init.copy(),
                tvec=tvec_init.copy(),
                useExtrinsicGuess=True,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if not ret:
                if DEBUG_PYRAMID:
                    print(f"  [REFINE] Standard PnP failed")
                return rvec_init, tvec_init, n_extra, reproj_before, None

        # Репроекционная ошибка ПОСЛЕ уточнения
        proj_after, _ = cv2.projectPoints(
            obj_pts_combined, rvec_ref, tvec_ref, camera_matrix, dist_coeffs
        )
        errors_after = np.linalg.norm(
            proj_after.reshape(-1, 2) - img_pts_combined.reshape(-1, 2), axis=1
        )
        reproj_after = float(np.mean(errors_after))
        median_error_after = float(np.median(errors_after))

        if DEBUG_PYRAMID:
            print(f"  [REFINE] After: mean={reproj_after:.2f}px, median={median_error_after:.2f}px")
            if inliers is not None:
                print(f"  [REFINE] RANSAC inliers: {len(inliers)}/{len(obj_pts_combined)}")

        # Критерии принятия уточнения:
        # 1. Ошибка не стала сильно хуже
        # 2. Медианная ошибка улучшилась или осталась такой же
        # 3. Абсолютная ошибка приемлема
        
        if reproj_after > reproj_before * 1.3:  # Улучшили порог с 1.5 до 1.3
            if DEBUG_PYRAMID:
                print(f"  [REFINE] Refinement worse (mean: {reproj_before:.2f}px -> {reproj_after:.2f}px), reverting")
            return rvec_init, tvec_init, n_extra, reproj_before, reproj_after
            
        if median_error_after > median_error_before * 1.2:
            if DEBUG_PYRAMID:
                print(f"  [REFINE] Median error worse ({median_error_before:.2f}px -> {median_error_after:.2f}px), reverting")
            return rvec_init, tvec_init, n_extra, reproj_before, reproj_after
            
        if reproj_after > 15.0:  # Абсолютный порог
            if DEBUG_PYRAMID:
                print(f"  [REFINE] Final error too high ({reproj_after:.2f}px > 15px), reverting")
            return rvec_init, tvec_init, n_extra, reproj_before, reproj_after

        if DEBUG_PYRAMID:
            print(f"  [REFINE] SUCCESS: {n_extra} extra pts, reproj {reproj_before:.2f}px -> {reproj_after:.2f}px")

        return rvec_ref, tvec_ref, n_extra, reproj_before, reproj_after

    except Exception as e:
        if DEBUG_PYRAMID:
            print(f"  [REFINE] Exception: {e}, using original pose")
        return rvec_init, tvec_init, n_extra, reproj_before, None
        
# ============================================================================
# КЛАСС ДЛЯ РАБОТЫ С 3D МОДЕЛЬЮ
# ============================================================================

class OBJModel:
    def __init__(self, filename):
        self.vertices = []
        self.faces = []
        self.filename = filename
        self.load_obj(filename)

    def load_obj(self, filename):
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('v '):
                        parts = line.strip().split()
                        self.vertices.append([
                            float(parts[1]) / 1000.0,
                            float(parts[2]) / 1000.0,
                            float(parts[3]) / 1000.0
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
            self.min_bounds = np.min(self.vertices, axis=0)
            self.max_bounds = np.max(self.vertices, axis=0)
            self.center = (self.min_bounds + self.max_bounds) / 2
            self.size = self.max_bounds - self.min_bounds
            self.diagonal = np.linalg.norm(self.size)
            self._print_statistics()

        except Exception as e:
            print(f"❌ OBJ load error: {e}")
            sys.exit(1)

    def _print_statistics(self):
        print(f"\n{'='*60}")
        print(f"📊 MODEL STATS: {os.path.basename(self.filename)}")
        print(f"{'='*60}")
        print(f"✅ Loaded: {len(self.vertices)} vertices, {len(self.faces)} faces")
        print(f"\n📐 BOUNDS (meters):")
        print(f"   Min: ({self.min_bounds[0]:.4f}, {self.min_bounds[1]:.4f}, {self.min_bounds[2]:.4f})")
        print(f"   Max: ({self.max_bounds[0]:.4f}, {self.max_bounds[1]:.4f}, {self.max_bounds[2]:.4f})")
        print(f"   Size (WxHxD): {self.size[0]:.4f} x {self.size[1]:.4f} x {self.size[2]:.4f}")
        print(f"   Diagonal: {self.diagonal:.4f} m")
        print(f"{'='*60}")

    def get_transform_matrix(self, scale, rot_x, rot_y, rot_z, offset_x, offset_y, offset_z):
        S = np.diag([scale, scale, scale, 1.0])
        Rx = np.eye(4)
        Ry = np.eye(4)
        Rz = np.eye(4)

        if rot_x != 0:
            rad = np.radians(rot_x)
            Rx[:3, :3] = [[1,0,0],[0,np.cos(rad),-np.sin(rad)],[0,np.sin(rad),np.cos(rad)]]
        if rot_y != 0:
            rad = np.radians(rot_y)
            Ry[:3, :3] = [[np.cos(rad),0,np.sin(rad)],[0,1,0],[-np.sin(rad),0,np.cos(rad)]]
        if rot_z != 0:
            rad = np.radians(rot_z)
            Rz[:3, :3] = [[np.cos(rad),-np.sin(rad),0],[np.sin(rad),np.cos(rad),0],[0,0,1]]

        R = Rz @ Ry @ Rx
        T = np.eye(4)
        T[:3, 3] = [offset_x, offset_y, offset_z]
        return T @ R @ S

    def transform(self, transform_matrix):
        if len(self.vertices) == 0:
            return None
        vertices_h = np.hstack([self.vertices, np.ones((len(self.vertices), 1))])
        transformed_h = (transform_matrix @ vertices_h.T).T
        return transformed_h[:, :3]


# ============================================================================
# КЛАСС КНОПКИ
# ============================================================================

class Button:
    def __init__(self, x, y, width, height, text,
                 color=(100,100,200), hover_color=(150,150,255),
                 toggle=False, active_color=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        # Для кнопок-переключателей
        self.toggle = toggle
        self.active = False
        self.active_color = active_color if active_color else (50, 200, 50)

    def draw(self, frame):
        if self.toggle and self.active:
            base_color = self.active_color
        else:
            base_color = self.color
        color = self.hover_color if self.is_hovered else base_color
        cv2.rectangle(frame, (self.x, self.y),
                      (self.x+self.width, self.y+self.height), color, -1)
        cv2.rectangle(frame, (self.x, self.y),
                      (self.x+self.width, self.y+self.height), (255,255,255), 2)
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        text_x = self.x + (self.width - text_size[0]) // 2
        text_y = self.y + (self.height + text_size[1]) // 2
        cv2.putText(frame, self.text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)

    def is_inside(self, x, y):
        return self.x <= x <= self.x+self.width and self.y <= y <= self.y+self.height


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

def save_config(config_file, params):
    try:
        params_with_time = params.copy()
        params_with_time['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(config_file, 'w') as f:
            json.dump(params_with_time, f, indent=4)
        print(f"\n💾 Config saved to {config_file}")
        return True
    except Exception as e:
        print(f"❌ Save error: {e}")
        return False

def load_config(config_file):
    try:
        if not os.path.exists(config_file):
            print(f"\n⚠️ File {config_file} not found")
            return None
        with open(config_file, 'r') as f:
            params = json.load(f)
        print(f"\n📂 Config loaded from {config_file}")
        return params
    except Exception as e:
        print(f"❌ Load error: {e}")
        return None

def slider_to_params(slider_values):
    params = {}
    if 'Scale_coarse' in slider_values:
        log_scale = -3 + (slider_values['Scale_coarse'] / 100) * 3.301
        params['scale'] = 10 ** log_scale
    if 'Scale_fine' in slider_values:
        fine_scale_factor = 1.0 + (slider_values['Scale_fine'] - 500) / 500.0 * 0.1
        if 'scale' in params:
            params['scale'] *= fine_scale_factor
    params['rot_x'] = slider_values.get('Rot X_coarse', 180) - 180
    params['rot_y'] = slider_values.get('Rot Y_coarse', 180) - 180
    params['rot_z'] = slider_values.get('Rot Z_coarse', 180) - 180
    params['rot_x'] += (slider_values.get('Rot X_fine', 500) - 500) / 100.0 * 5
    params['rot_y'] += (slider_values.get('Rot Y_fine', 500) - 500) / 100.0 * 5
    params['rot_z'] += (slider_values.get('Rot Z_fine', 500) - 500) / 100.0 * 5
    params['offset_x'] = (slider_values.get('Offset X_coarse', 500) - 500) / 100.0
    params['offset_y'] = (slider_values.get('Offset Y_coarse', 500) - 500) / 100.0
    params['offset_z'] = (slider_values.get('Offset Z_coarse', 500) - 500) / 100.0
    params['offset_x'] += (slider_values.get('Offset X_fine', 500) - 500) / 500.0 * 0.05
    params['offset_y'] += (slider_values.get('Offset Y_fine', 500) - 500) / 500.0 * 0.05
    params['offset_z'] += (slider_values.get('Offset Z_fine', 500) - 500) / 500.0 * 0.05
    params['mode'] = slider_values.get('Mode', 1)
    return params

def params_to_slider(params):
    slider_values = {}
    if 'scale' in params:
        scale = max(0.001, min(2.0, params['scale']))
        log_scale = np.log10(scale)
        slider_values['Scale_coarse'] = int((log_scale + 3) * 100 / 3.301)
        slider_values['Scale_fine'] = 500
    slider_values['Rot X_coarse'] = int(params.get('rot_x', 0) + 180)
    slider_values['Rot Y_coarse'] = int(params.get('rot_y', 0) + 180)
    slider_values['Rot Z_coarse'] = int(params.get('rot_z', 0) + 180)
    slider_values['Rot X_fine'] = 500
    slider_values['Rot Y_fine'] = 500
    slider_values['Rot Z_fine'] = 500
    slider_values['Offset X_coarse'] = int(params.get('offset_x', 0) * 100 + 500)
    slider_values['Offset Y_coarse'] = int(params.get('offset_y', 0) * 100 + 500)
    slider_values['Offset Z_coarse'] = int(params.get('offset_z', 0) * 100 + 500)
    slider_values['Offset X_fine'] = 500
    slider_values['Offset Y_fine'] = 500
    slider_values['Offset Z_fine'] = 500
    slider_values['Mode'] = int(params.get('mode', 1))
    return slider_values


# ============================================================================
# APRILTAG УТИЛИТЫ
# ============================================================================

def rotation_vector_to_euler(rvec):
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
    R, _ = cv2.Rodrigues(rvec)
    R_flip = np.array([[1,0,0],[0,-1,0],[0,0,-1]])
    R_corrected = R @ R_flip
    rvec_corrected, _ = cv2.Rodrigues(R_corrected)
    return rvec_corrected, tvec


# ============================================================================
# КАМЕРА
# ============================================================================

def init_camera():
    global camera_matrix, dist_coeffs, width, height, cap, picam2

    print(f"\n📹 CAMERA INIT")
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
        print(f"✅ USB camera: {width}x{height}")
    else:
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
        print(f"✅ CSI camera: {width}x{height}")

    if width != CALIB_WIDTH:
        scale = width / CALIB_WIDTH
        camera_matrix[0,0] *= scale
        camera_matrix[1,1] *= scale
        camera_matrix[0,2] *= scale
        camera_matrix[1,2] *= scale
        print(f"✅ Camera matrix scaled x{scale:.2f}")

def get_frame():
    if CAMERA_TYPE == 'usb':
        ret, frame = cap.read()
        if not ret:
            return None
        return frame
    else:
        return picam2.capture_array()

def resize_frame_to_display(frame, target_width, target_height):
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
# ОТРИСОВКА ТОЧЕК ПЕРЕСЕЧЕНИЯ ЛИНИЙ
# ============================================================================

def draw_pyramid_corners(frame, pyramid_results, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Отрисовывает на кадре проекции центров граней и найденные точки пересечения линий.
    """
    face_colors = {
        'FRONT': (0,   255, 255),   # жёлтый
        'BACK':  (255, 128, 0  ),   # голубой
        'LEFT':  (0,   255, 0  ),   # зелёный
        'RIGHT': (128, 0,   255),   # фиолетовый
    }

    for r in pyramid_results:
        color = face_colors.get(r['face'], (200, 200, 200))
        px, py = int(r['proj_2d'][0]), int(r['proj_2d'][1])

        # Проецированный центр грани — пунктирный круг
        if 0 <= px < frame.shape[1] and 0 <= py < frame.shape[0]:
            cv2.circle(frame, (px, py), 8, color, 1)
            cv2.drawMarker(frame, (px, py), color,
                           cv2.MARKER_CROSS, 12, 1, cv2.LINE_AA)
            # Подпись грани
            cv2.putText(frame, r['face'][0],  # первая буква названия
                        (px+10, py-5), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, color, 1, cv2.LINE_AA)

        # Найденная субпиксельная точка — закрашенный круг (только если точка найдена)
        if r['corner_2d'] is not None:
            cx, cy = int(r['corner_2d'][0]), int(r['corner_2d'][1])
            if 0 <= cx < frame.shape[1] and 0 <= cy < frame.shape[0]:
                cv2.circle(frame, (cx, cy), 5, color, -1)
                cv2.circle(frame, (cx, cy), 7, (255, 255, 255), 1)
                # Линия от проекции к найденной точке
                if 0 <= px < frame.shape[1] and 0 <= py < frame.shape[0]:
                    cv2.line(frame, (px, py), (cx, cy), color, 1, cv2.LINE_AA)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    print(f"\n{'='*60}")
    print(f"🚀 APRILTAG 3D MODEL VIEWER + PYRAMID REFINE (LINE CROSS DETECTOR)")
    print(f"{'='*60}")
    print(f"\n[PYRAMID CONFIG]")
    print(f"  Base: {PYRAMID_BASE_SIZE}mm, Top: {PYRAMID_TOP_SIZE}mm")
    print(f"  Angle: {PYRAMID_ANGLE_DEG}°, Height: {PYRAMID_HEIGHT:.2f}mm")
    print(f"  Line width: {LINE_WIDTH}mm")
    print(f"  Debug: {DEBUG_PYRAMID}")

    scale_x = 1.0
    scale_y = 1.0
    fullscreen_mode = False

    init_camera()

    model = OBJModel(MODEL_PATH)

    print(f"\n🎯 APRILTAG INIT")
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
    print(f"✅ Detector ready, target ID: {TARGET_MARKER_ID}")

    print(f"\n⚙️ LOADING CONFIG")
    print(f"{'='*50}")
    config = load_config(CONFIG_FILE)
    if config:
        slider_defaults = params_to_slider(config)
    else:
        slider_defaults = {
            'Scale_coarse': 50, 'Scale_fine': 500,
            'Rot X_coarse': 180, 'Rot Y_coarse': 180, 'Rot Z_coarse': 180,
            'Rot X_fine': 500, 'Rot Y_fine': 500, 'Rot Z_fine': 500,
            'Offset X_coarse': 500, 'Offset Y_coarse': 500, 'Offset Z_coarse': 500,
            'Offset X_fine': 500, 'Offset Y_fine': 500, 'Offset Z_fine': 500,
            'Mode': 1
        }

    # ===== ОКНА =====
    window_main = 'AprilTag Camera View'
    window_controls = 'Controls'

    cv2.namedWindow(window_main, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_main, DISPLAY_WIDTH, DISPLAY_HEIGHT)
    cv2.moveWindow(window_main, 0, 0)

    cv2.namedWindow(window_controls, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_controls, 500, 700)
    cv2.moveWindow(window_controls, DISPLAY_WIDTH - 500, 0)

    def nothing(x):
        pass

    cv2.createTrackbar('Scale_coarse',    window_controls, slider_defaults['Scale_coarse'],    100,  nothing)
    cv2.createTrackbar('Rot X_coarse',    window_controls, slider_defaults['Rot X_coarse'],    360,  nothing)
    cv2.createTrackbar('Rot Y_coarse',    window_controls, slider_defaults['Rot Y_coarse'],    360,  nothing)
    cv2.createTrackbar('Rot Z_coarse',    window_controls, slider_defaults['Rot Z_coarse'],    360,  nothing)
    cv2.createTrackbar('Offset X_coarse', window_controls, slider_defaults['Offset X_coarse'], 1000, nothing)
    cv2.createTrackbar('Offset Y_coarse', window_controls, slider_defaults['Offset Y_coarse'], 1000, nothing)
    cv2.createTrackbar('Offset Z_coarse', window_controls, slider_defaults['Offset Z_coarse'], 1000, nothing)
    cv2.createTrackbar('Scale_fine',      window_controls, slider_defaults['Scale_fine'],      1000, nothing)
    cv2.createTrackbar('Rot X_fine',      window_controls, slider_defaults['Rot X_fine'],      1000, nothing)
    cv2.createTrackbar('Rot Y_fine',      window_controls, slider_defaults['Rot Y_fine'],      1000, nothing)
    cv2.createTrackbar('Rot Z_fine',      window_controls, slider_defaults['Rot Z_fine'],      1000, nothing)
    cv2.createTrackbar('Offset X_fine',   window_controls, slider_defaults['Offset X_fine'],   1000, nothing)
    cv2.createTrackbar('Offset Y_fine',   window_controls, slider_defaults['Offset Y_fine'],   1000, nothing)
    cv2.createTrackbar('Offset Z_fine',   window_controls, slider_defaults['Offset Z_fine'],   1000, nothing)
    cv2.createTrackbar('Mode: 0pts/1wire/2face', window_controls, slider_defaults['Mode'], 2, nothing)

    # ===== КНОПКИ =====
    # Порядок: [MODEL] [SAVE] [LOAD] [RESET] [ATTACH] [REFINE] [FULL] [EXIT]
    button_width  = 100
    button_height = 40
    margin = 10
    n_buttons = 8
    start_x = width - (button_width + margin) * n_buttons

    buttons = [
        Button(start_x + (button_width+margin)*0, 10, button_width, button_height,
               "MODEL",  (80,80,80),    (130,130,130),
               toggle=True, active_color=(50,150,50)),
        Button(start_x + (button_width+margin)*1, 10, button_width, button_height,
               "SAVE",   (50,150,50),   (100,255,100)),
        Button(start_x + (button_width+margin)*2, 10, button_width, button_height,
               "LOAD",   (50,50,150),   (100,100,255)),
        Button(start_x + (button_width+margin)*3, 10, button_width, button_height,
               "RESET",  (150,150,50),  (255,255,100)),
        Button(start_x + (button_width+margin)*4, 10, button_width, button_height,
               "ATTACH", (150,50,150),  (255,100,255)),
        Button(start_x + (button_width+margin)*5, 10, button_width, button_height,
               "REFINE", (30,80,160),   (60,140,255),
               toggle=True, active_color=(0,160,220)),
        Button(start_x + (button_width+margin)*6, 10, button_width, button_height,
               "FULL",   (100,100,100), (150,150,150)),
        Button(start_x + (button_width+margin)*7, 10, button_width, button_height,
               "EXIT",   (150,50,50),   (255,100,100)),
    ]

    # Кнопка MODEL по умолчанию активна (модель показывается)
    buttons[0].active = True

    # Предвычисление рёбер
    print(f"\n🔧 PREPARING DATA")
    print(f"{'='*50}")
    edges = set()
    for face in model.faces:
        for i in range(len(face)):
            edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
            edges.add(edge)
    edges = list(edges)
    print(f"✅ {len(edges)} edges computed")

    # 3D координаты углов AprilTag для PnP (в мм, Z=0)
    half = MARKER_SIZE / 2.0
    apriltag_obj_pts = np.array([
        [-half, -half, 0.0],
        [ half, -half, 0.0],
        [ half,  half, 0.0],
        [-half,  half, 0.0],
    ], dtype=np.float32)

    # Переменные состояния
    marker_detected       = False
    last_known_rvec       = None
    last_known_tvec       = None
    last_apriltag_corners = None
    auto_center_requested = False
    pyramid_results_cache = []
    n_pyramid_found       = 0
    refine_reproj_info    = (None, None)

    last_time = time.time()
    frame_count = 0
    fps = 0

    print(f"\n{'='*60}")
    print(f"🚀 MAIN LOOP STARTED")
    print(f"{'='*60}")
    print(f"📸 Resolution: {width}x{height}")
    print(f"🎯 Target marker ID: {TARGET_MARKER_ID}")
    print(f"🔲 Pyramid: base={PYRAMID_BASE_SIZE}mm, h={PYRAMID_HEIGHT:.1f}mm")
    print(f"\nButtons: [MODEL] show/hide 3D model")
    print(f"         [REFINE] enable pyramid corner refinement")
    print(f"\n{'='*60}\n")

    # ----- Mouse callback -----
    def mouse_callback(event, x, y, flags, param):
        nonlocal fullscreen_mode, auto_center_requested

        _scale_x  = param['scale_x']
        _scale_y  = param['scale_y']
        _offset_x = param['offset_x']
        _offset_y = param['offset_y']
        _buttons  = param['buttons']

        orig_x = int((x - _offset_x) / _scale_x)
        orig_y = int((y - _offset_y) / _scale_y)

        if orig_x < 0 or orig_y < 0 or orig_x >= width or orig_y >= height:
            return

        for btn in _buttons:
            btn.is_hovered = btn.is_inside(orig_x, orig_y)

        if event == cv2.EVENT_LBUTTONDOWN:
            for btn in _buttons:
                if not btn.is_inside(orig_x, orig_y):
                    continue

                if btn.text == "MODEL":
                    btn.active = not btn.active
                    print(f"\n👁️ Model display: {'ON' if btn.active else 'OFF'}")

                elif btn.text == "REFINE":
                    btn.active = not btn.active
                    print(f"\n🔺 Pyramid refinement: {'ON' if btn.active else 'OFF'}")

                elif btn.text == "SAVE":
                    slider_vals = _get_all_sliders()
                    params = slider_to_params(slider_vals)
                    save_config(CONFIG_FILE, params)

                elif btn.text == "LOAD":
                    p = load_config(CONFIG_FILE)
                    if p:
                        sv = params_to_slider(p)
                        _set_all_sliders(sv)

                elif btn.text == "RESET":
                    _reset_sliders()
                    print("\n🔄 Sliders reset")

                elif btn.text == "ATTACH":
                    if marker_detected:
                        print("\n🔗 Attaching model to marker...")
                        auto_center_requested = True
                    else:
                        print("\n⚠️ Marker not detected, cannot attach")

                elif btn.text == "FULL":
                    fullscreen_mode = not fullscreen_mode
                    if fullscreen_mode:
                        cv2.setWindowProperty(window_main, cv2.WND_PROP_FULLSCREEN,
                                              cv2.WINDOW_FULLSCREEN)
                        cv2.resizeWindow(window_controls, 1, 1)
                        cv2.moveWindow(window_controls, -1000, -1000)
                    else:
                        cv2.setWindowProperty(window_main, cv2.WND_PROP_FULLSCREEN,
                                              cv2.WINDOW_NORMAL)
                        cv2.resizeWindow(window_main, DISPLAY_WIDTH, DISPLAY_HEIGHT)
                        cv2.moveWindow(window_main, 0, 0)
                        cv2.resizeWindow(window_controls, 500, 700)
                        cv2.moveWindow(window_controls, DISPLAY_WIDTH-500, 0)

                elif btn.text == "EXIT":
                    print("\n👋 Exit...")
                    cv2.destroyAllWindows()
                    sys.exit(0)

    def _get_all_sliders():
        return {
            'Scale_coarse':    cv2.getTrackbarPos('Scale_coarse',    window_controls),
            'Scale_fine':      cv2.getTrackbarPos('Scale_fine',      window_controls),
            'Rot X_coarse':    cv2.getTrackbarPos('Rot X_coarse',    window_controls),
            'Rot Y_coarse':    cv2.getTrackbarPos('Rot Y_coarse',    window_controls),
            'Rot Z_coarse':    cv2.getTrackbarPos('Rot Z_coarse',    window_controls),
            'Rot X_fine':      cv2.getTrackbarPos('Rot X_fine',      window_controls),
            'Rot Y_fine':      cv2.getTrackbarPos('Rot Y_fine',      window_controls),
            'Rot Z_fine':      cv2.getTrackbarPos('Rot Z_fine',      window_controls),
            'Offset X_coarse': cv2.getTrackbarPos('Offset X_coarse', window_controls),
            'Offset Y_coarse': cv2.getTrackbarPos('Offset Y_coarse', window_controls),
            'Offset Z_coarse': cv2.getTrackbarPos('Offset Z_coarse', window_controls),
            'Offset X_fine':   cv2.getTrackbarPos('Offset X_fine',   window_controls),
            'Offset Y_fine':   cv2.getTrackbarPos('Offset Y_fine',   window_controls),
            'Offset Z_fine':   cv2.getTrackbarPos('Offset Z_fine',   window_controls),
            'Mode':            cv2.getTrackbarPos('Mode: 0pts/1wire/2face', window_controls),
        }

    def _set_all_sliders(sv):
        cv2.setTrackbarPos('Scale_coarse',    window_controls, sv['Scale_coarse'])
        cv2.setTrackbarPos('Scale_fine',      window_controls, sv['Scale_fine'])
        cv2.setTrackbarPos('Rot X_coarse',    window_controls, sv['Rot X_coarse'])
        cv2.setTrackbarPos('Rot Y_coarse',    window_controls, sv['Rot Y_coarse'])
        cv2.setTrackbarPos('Rot Z_coarse',    window_controls, sv['Rot Z_coarse'])
        cv2.setTrackbarPos('Rot X_fine',      window_controls, sv['Rot X_fine'])
        cv2.setTrackbarPos('Rot Y_fine',      window_controls, sv['Rot Y_fine'])
        cv2.setTrackbarPos('Rot Z_fine',      window_controls, sv['Rot Z_fine'])
        cv2.setTrackbarPos('Offset X_coarse', window_controls, sv['Offset X_coarse'])
        cv2.setTrackbarPos('Offset Y_coarse', window_controls, sv['Offset Y_coarse'])
        cv2.setTrackbarPos('Offset Z_coarse', window_controls, sv['Offset Z_coarse'])
        cv2.setTrackbarPos('Offset X_fine',   window_controls, sv['Offset X_fine'])
        cv2.setTrackbarPos('Offset Y_fine',   window_controls, sv['Offset Y_fine'])
        cv2.setTrackbarPos('Offset Z_fine',   window_controls, sv['Offset Z_fine'])
        cv2.setTrackbarPos('Mode: 0pts/1wire/2face', window_controls, sv['Mode'])

    def _reset_sliders():
        _set_all_sliders({
            'Scale_coarse': 50, 'Scale_fine': 500,
            'Rot X_coarse': 180, 'Rot Y_coarse': 180, 'Rot Z_coarse': 180,
            'Rot X_fine': 500, 'Rot Y_fine': 500, 'Rot Z_fine': 500,
            'Offset X_coarse': 500, 'Offset Y_coarse': 500, 'Offset Z_coarse': 500,
            'Offset X_fine': 500, 'Offset Y_fine': 500, 'Offset Z_fine': 500,
            'Mode': 1,
        })

    mouse_param = {
        'buttons': buttons,
        'scale_x': 1.0, 'scale_y': 1.0,
        'offset_x': 0,  'offset_y': 0,
    }
    cv2.setMouseCallback(window_main, mouse_callback, mouse_param)

    # Найти кнопки по имени для удобного доступа
    def get_btn(name):
        for b in buttons:
            if b.text == name:
                return b
        return None

    btn_model  = get_btn("MODEL")
    btn_refine = get_btn("REFINE")

    # ===== ОСНОВНОЙ ЦИКЛ =====
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

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # --- Детектирование AprilTag ---
            detections = detector.detect(
                gray,
                estimate_tag_pose=True,
                camera_params=[camera_matrix[0,0], camera_matrix[1,1],
                               camera_matrix[0,2], camera_matrix[1,2]],
                tag_size=MARKER_SIZE / 1000.0
            )

            target_rvec       = None
            target_tvec       = None
            target_img_corners = None
            tag_info          = "No tag detected"

            for detection in detections:
                corners = np.array(detection.corners, dtype=np.int32)
                color = (0,255,255) if detection.tag_id == TARGET_MARKER_ID else (0,255,0)
                cv2.polylines(frame, [corners], True, color, 3)

                rvec, _ = cv2.Rodrigues(detection.pose_R)
                tvec = np.array(detection.pose_t).reshape(3, 1)
                rvec, tvec = flip_z_axis(rvec, tvec)

                if detection.tag_id == TARGET_MARKER_ID:
                    target_rvec        = rvec
                    target_tvec        = tvec
                    target_img_corners = np.array(detection.corners, dtype=np.float32)  # (4,2)
                    marker_detected    = True
                    last_known_rvec    = rvec.copy()
                    last_known_tvec    = tvec.copy()
                    last_apriltag_corners = target_img_corners.copy()

                    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, 0.05)

                    roll, pitch, yaw = rotation_vector_to_euler(rvec)
                    distance = np.linalg.norm(tvec)
                    tag_info = (f"Tag ID:{detection.tag_id} | D:{distance:.2f}m | "
                                f"R:{roll:.1f} P:{pitch:.1f} Y:{yaw:.1f}")

                    if auto_center_requested:
                        center_3d = np.array([[0,0,0]], dtype=np.float32)
                        center_2d, _ = cv2.projectPoints(
                            center_3d, rvec, tvec, camera_matrix, dist_coeffs)
                        center_2d = center_2d[0][0]
                        dx = width//2 - center_2d[0]
                        dy = height//2 - center_2d[1]
                        print(f"   Offset to center: ({dx:.0f}, {dy:.0f}) px")
                        auto_center_requested = False

            # Использовать последнюю известную позу если маркер не виден
            if target_rvec is None and last_known_rvec is not None:
                target_rvec        = last_known_rvec
                target_tvec        = last_known_tvec
                target_img_corners = last_apriltag_corners
                tag_info = "WARNING: USING LAST KNOWN POSITION"

            # ================================================================
            # УТОЧНЕНИЕ ПОЗЫ ПО ТОЧКАМ ПЕРЕСЕЧЕНИЯ ЛИНИЙ (только если REFINE ON)
            # ================================================================
            refine_active = btn_refine is not None and btn_refine.active

            if refine_active and target_rvec is not None and target_img_corners is not None:
                if DEBUG_PYRAMID:
                    print(f"\n[PYRAMID DEBUG] Frame {frame_count}:")

                # Детектируем точки пересечения линий на гранях
                pyramid_results_cache = detect_pyramid_corners(
                    gray, target_rvec, target_tvec, camera_matrix, dist_coeffs
                )

                # Подсчёт найденных точек
                n_pyramid_found = sum(1 for r in pyramid_results_cache
                                      if r['corner_2d'] is not None)

                # Уточняем позу
                (target_rvec, target_tvec,
                 n_used, reproj_before, reproj_after) = refine_pose_with_pyramid_corners(
                    target_rvec, target_tvec,
                    apriltag_obj_pts,
                    target_img_corners,
                    pyramid_results_cache,
                    camera_matrix, dist_coeffs
                )
                refine_reproj_info = (reproj_before, reproj_after)

                # Отрисовка точек пирамиды (только найденные точки будут нарисованы)
                draw_pyramid_corners(frame, pyramid_results_cache,
                                     target_rvec, target_tvec,
                                     camera_matrix, dist_coeffs)
            else:
                pyramid_results_cache = []
                n_pyramid_found = 0
                refine_reproj_info = (None, None)

            # ================================================================
            # СЛАЙДЕРЫ
            # ================================================================
            slider_vals = _get_all_sliders()
            params = slider_to_params(slider_vals)

            # ================================================================
            # ОТРИСОВКА 3D МОДЕЛИ (только если MODEL ON)
            # ================================================================
            show_model = btn_model is not None and btn_model.active

            if show_model and target_rvec is not None:
                T_model_tag = model.get_transform_matrix(
                    params['scale'],
                    params['rot_x'], params['rot_y'], params['rot_z'],
                    params['offset_x'], params['offset_y'], params['offset_z']
                )

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
                            cv2.circle(frame, tuple(pt), 2, (0,255,255), -1)

                elif mode == 1:
                    for edge in edges:
                        if edge[0] < len(img_points) and edge[1] < len(img_points):
                            pt1 = img_points[edge[0]]
                            pt2 = img_points[edge[1]]
                            if (0 <= pt1[0] < width and 0 <= pt1[1] < height and
                                    0 <= pt2[0] < width and 0 <= pt2[1] < height):
                                cv2.line(frame, tuple(pt1), tuple(pt2), (0,255,0), 1)

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
                                cv2.fillPoly(frame, [pts], (100,100,255))

            # ================================================================
            # КНОПКИ
            # ================================================================
            for btn in buttons:
                btn.draw(frame)

            # ================================================================
            # ИНФОРМАЦИЯ НА КАДРЕ
            # ================================================================
            refine_str = ""
            if refine_active:
                rb, ra = refine_reproj_info
                if rb is not None and ra is not None:
                    refine_str = f"Lines: {n_pyramid_found}/4 pts | reproj {rb:.1f}->{ra:.1f}px"
                elif rb is not None:
                    refine_str = f"Lines: {n_pyramid_found}/4 pts | reproj {rb:.1f}px (no refine)"
                else:
                    refine_str = f"Lines: {n_pyramid_found}/4 pts"

            info_lines = [
                f"FPS: {fps:.1f}  |  Model: {'ON' if show_model else 'OFF'}  |  Refine: {'ON' if refine_active else 'OFF'}",
                f"Target ID: {TARGET_MARKER_ID}",
                tag_info,
                f"Scale: {params['scale']:.6f}",
                f"Rot: {params['rot_x']:6.2f} {params['rot_y']:6.2f} {params['rot_z']:6.2f} deg",
                f"Offset: X:{params['offset_x']:+.4f} Y:{params['offset_y']:+.4f} Z:{params['offset_z']:+.4f}m",
            ]
            if refine_str:
                info_lines.append(refine_str)

            y_pos = height - len(info_lines) * 22 - 10
            for line in info_lines:
                cv2.putText(frame, line, (10, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                y_pos += 22

            # ================================================================
            # ПОКАЗ КАДРА
            # ================================================================
            display_frame, scale_x, scale_y, x_offset, y_offset, disp_w, disp_h = \
                resize_frame_to_display(frame, DISPLAY_WIDTH, DISPLAY_HEIGHT)

            mouse_param['scale_x']  = scale_x
            mouse_param['scale_y']  = scale_y
            mouse_param['offset_x'] = x_offset
            mouse_param['offset_y'] = y_offset

            cv2.imshow(window_main, display_frame)

            # ================================================================
            # ОКНО УПРАВЛЕНИЯ
            # ================================================================
            controls_frame = np.zeros((700, 500, 3), dtype=np.uint8)

            cv2.putText(controls_frame, "CONTROL PANEL", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

            cv2.putText(controls_frame, "=== COARSE ADJUSTMENT ===", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,255), 1)
            cv2.putText(controls_frame, "=== FINE ADJUSTMENT ===", (20, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,200,200), 1)
            cv2.putText(controls_frame, "Scale: +-10%", (20, 320),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
            cv2.putText(controls_frame, "Rot: +-5 deg", (20, 340),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
            cv2.putText(controls_frame, "Offset: +-0.05m", (20, 360),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)

            cv2.putText(controls_frame, f"Target ID: {TARGET_MARKER_ID}", (20, 400),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
            cv2.putText(controls_frame,
                        f"Detected: {'YES' if marker_detected else 'NO'}", (20, 420),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0,255,0) if marker_detected else (0,0,255), 1)

            # Статус REFINE
            refine_color = (0,220,255) if refine_active else (120,120,120)
            cv2.putText(controls_frame,
                        f"Line cross refine: {'ACTIVE' if refine_active else 'OFF'}",
                        (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, refine_color, 1)
            if refine_active:
                cv2.putText(controls_frame,
                            f"Line crosses found: {n_pyramid_found}/4", (20, 470),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
                rb, ra = refine_reproj_info
                if rb is not None:
                    cv2.putText(controls_frame,
                                f"Reproj: {rb:.2f}px -> {ra:.2f}px" if ra else
                                f"Reproj before: {rb:.2f}px",
                                (20, 490), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)

            cv2.putText(controls_frame, "Current fine values:", (20, 520),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
            cv2.putText(controls_frame,
                        f"Scale fine: {(slider_vals['Scale_fine']-500)/500*10:+.1f}%",
                        (20, 540), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
            cv2.putText(controls_frame,
                        f"Rot fine: X{(slider_vals['Rot X_fine']-500)/100*5:+5.2f}"
                        f" Y{(slider_vals['Rot Y_fine']-500)/100*5:+5.2f}"
                        f" Z{(slider_vals['Rot Z_fine']-500)/100*5:+5.2f} deg",
                        (20, 560), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)
            cv2.putText(controls_frame,
                        f"Offset fine:"
                        f" X{(slider_vals['Offset X_fine']-500)/500*0.05:+6.3f}"
                        f" Y{(slider_vals['Offset Y_fine']-500)/500*0.05:+6.3f}"
                        f" Z{(slider_vals['Offset Z_fine']-500)/500*0.05:+6.3f}m",
                        (20, 580), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)

            # Параметры пирамиды
            cv2.putText(controls_frame,
                        f"Pyramid: base={PYRAMID_BASE_SIZE}mm top={PYRAMID_TOP_SIZE}mm"
                        f" h={PYRAMID_HEIGHT:.1f}mm a={PYRAMID_ANGLE_DEG}deg",
                        (20, 620), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150,150,150), 1)
            
            if WINDOWS_CONTROL_EN:
                cv2.imshow(window_controls, controls_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n👋 Shutting down...")
        if CAMERA_TYPE == 'usb' and cap:
            cap.release()
        elif picam2:
            picam2.stop()
        cv2.destroyAllWindows()
        print("✅ Done")


if __name__ == "__main__":
    main()