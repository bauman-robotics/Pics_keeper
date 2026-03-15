"""
Утилиты для визуализации - функции для отрисовки маркеров, осей и информации


Этот файл содержит все необходимые функции для визуализации:
    draw_axes_standard - стандартная отрисовка осей OpenCV (как в исходном коде)
    draw_axes_with_check - отрисовка с проверкой видимости
    draw_marker_corners - отрисовка углов маркера
    draw_info_panel - информационная панель
    draw_debug_points - отладочные точки
    draw_coordinate_grid - координатная сетка
    draw_axis_vectors - векторы осей
"""
import numpy as np
import cv2


def draw_axes_with_check(frame, rvec, tvec, camera_matrix, dist_coeffs, size=0.05):
    """
    Рисование осей координат с проверкой видимости и ограничением длины
    
    Args:
        frame: кадр для отрисовки
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        size: длина оси в метрах
    """
    h, w = frame.shape[:2]
    
    # Точки для осей
    axis_points = np.array([
        [0, 0, 0],      # начало координат
        [size, 0, 0],   # ось X
        [0, size, 0],   # ось Y
        [0, 0, size]    # ось Z
    ], dtype=np.float32)
    
    # Проекция точек
    img_points, _ = cv2.projectPoints(
        axis_points, rvec, tvec, camera_matrix, dist_coeffs
    )
    img_points = img_points.reshape(-1, 2)
    
    # Проверяем, что начало координат в кадре
    origin = img_points[0]
    if not (0 <= origin[0] < w and 0 <= origin[1] < h):
        # Маркер вне кадра - рисуем предупреждение
        cv2.putText(frame, "Marker outside frame", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame
    
    # Цвета осей (BGR)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # X-синий, Y-зеленый, Z-красный
    labels = ['X', 'Y', 'Z']
    
    for i in range(1, 4):  # для каждой оси
        start_point = (int(origin[0]), int(origin[1]))
        end_point = (int(img_points[i][0]), int(img_points[i][1]))
        
        # Вычисляем направление вектора
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        
        # Если ось слишком длинная, нормализуем
        length = np.sqrt(dx*dx + dy*dy)
        if length > min(w, h) * 0.3:  # если больше 30% экрана
            if length > 0:
                scale = min(w, h) * 0.15 / length
                dx = int(dx * scale)
                dy = int(dy * scale)
                end_point = (start_point[0] + dx, start_point[1] + dy)
        
        # Проверяем, что конечная точка в пределах кадра
        end_point = (
            max(0, min(w-1, end_point[0])),
            max(0, min(h-1, end_point[1]))
        )
        
        # Рисуем ось
        cv2.arrowedLine(frame, start_point, end_point, 
                       colors[i-1], 2, tipLength=0.2)
        
        # Подпись оси
        label_pos = (end_point[0] + 5, end_point[1] - 5)
        cv2.putText(frame, labels[i-1], label_pos,
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[i-1], 2)
    
    return frame


def draw_marker_corners(frame, corners, detected_id, target_id):
    """
    Рисование углов маркера
    
    Args:
        frame: кадр
        corners: углы маркера (4 точки)
        detected_id: ID обнаруженного маркера
        target_id: ID целевого маркера
    """
    color = (0, 255, 255) if detected_id == target_id else (0, 255, 0)
    corners_int = corners.astype(np.int32)
    
    # Рисуем контур
    cv2.polylines(frame, [corners_int], True, color, 3)
    
    # Рисуем углы
    for i, corner in enumerate(corners_int):
        cv2.circle(frame, tuple(corner), 5, color, -1)
        cv2.putText(frame, str(i), (corner[0] + 5, corner[1] - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def draw_info_panel(frame, fps, marker_detected, distance, 
                   roll, pitch, yaw, n_pyramid_found=0):
    """
    Рисование информационной панели
    
    Args:
        frame: кадр
        fps: количество кадров в секунду
        marker_detected: обнаружен ли маркер
        distance: расстояние до маркера
        roll, pitch, yaw: углы поворота
        n_pyramid_found: количество найденных точек пирамиды
    """
    h, w = frame.shape[:2]
    
    # Полупрозрачный фон для текста
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (350, 150), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    
    # Информация
    y_pos = 30
    cv2.putText(frame, f"FPS: {fps:.1f}", (20, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y_pos += 25
    
    status = "DETECTED" if marker_detected else "NOT FOUND"
    color = (0, 255, 0) if marker_detected else (0, 0, 255)
    cv2.putText(frame, f"Marker: {status}", (20, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    y_pos += 25
    
    if marker_detected:
        cv2.putText(frame, f"Distance: {distance:.2f}m", (20, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_pos += 25
        
        cv2.putText(frame, f"Rot: R{roll:5.1f} P{pitch:5.1f} Y{yaw:5.1f}", 
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_pos += 25
        
        if n_pyramid_found > 0:
            cv2.putText(frame, f"Pyramid: {n_pyramid_found}/4", 
                       (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    return frame


def draw_debug_points(frame, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Рисование отладочных точек для проверки проекции
    
    Args:
        frame: кадр
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
    """
    h, w = frame.shape[:2]
    
    # Точки для проверки (углы маркера и центр)
    test_points = np.array([
        [-0.025, -0.025, 0],  # левый верхний угол
        [ 0.025, -0.025, 0],  # правый верхний угол
        [ 0.025,  0.025, 0],  # правый нижний угол
        [-0.025,  0.025, 0],  # левый нижний угол
        [0, 0, 0]              # центр
    ], dtype=np.float32)
    
    # Проекция точек
    img_points, _ = cv2.projectPoints(
        test_points, rvec, tvec, camera_matrix, dist_coeffs
    )
    img_points = img_points.reshape(-1, 2).astype(int)
    
    # Рисуем сетку
    for i in range(4):
        pt1 = tuple(img_points[i])
        pt2 = tuple(img_points[(i+1)%4])
        cv2.line(frame, pt1, pt2, (255, 255, 0), 1)
    
    # Центр маркера
    cv2.circle(frame, tuple(img_points[4]), 8, (0, 255, 255), -1)
    
    return frame


def draw_axes_standard(frame, rvec, tvec, camera_matrix, dist_coeffs, size=0.05):
    """
    Стандартное рисование осей с помощью OpenCV (как в исходном коде)
    
    Args:
        frame: кадр для отрисовки
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        size: длина оси в метрах
    """
    cv2.drawFrameAxes(frame, camera_matrix, dist_coeffs, rvec, tvec, size)
    return frame


def draw_coordinate_grid(frame, rvec, tvec, camera_matrix, dist_coeffs, size=0.1, step=0.02):
    """
    Рисование координатной сетки на плоскости маркера
    
    Args:
        frame: кадр
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        size: размер сетки
        step: шаг сетки
    """
    # Создаем точки сетки
    points = []
    x = np.arange(-size/2, size/2 + step, step)
    y = np.arange(-size/2, size/2 + step, step)
    
    for xi in x:
        for yi in y:
            points.append([xi, yi, 0])
    
    points = np.array(points, dtype=np.float32)
    
    # Проекция точек
    img_points, _ = cv2.projectPoints(
        points, rvec, tvec, camera_matrix, dist_coeffs
    )
    img_points = img_points.reshape(-1, 2).astype(int)
    
    # Рисуем точки
    for pt in img_points:
        cv2.circle(frame, tuple(pt), 1, (100, 100, 100), -1)
    
    return frame


def draw_axis_vectors(frame, rvec, tvec, camera_matrix, dist_coeffs, size=0.05):
    """
    Рисование осей с отображением векторов направления
    
    Args:
        frame: кадр
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        size: длина оси
    """
    h, w = frame.shape[:2]
    
    # Получаем матрицу поворота
    R, _ = cv2.Rodrigues(rvec)
    
    # Направления осей в системе координат маркера
    axes_directions = np.array([
        [size, 0, 0],   # X
        [0, size, 0],   # Y
        [0, 0, size]    # Z
    ], dtype=np.float32)
    
    # Проецируем начало координат
    origin_point = np.array([[0, 0, 0]], dtype=np.float32)
    origin_2d, _ = cv2.projectPoints(
        origin_point, rvec, tvec, camera_matrix, dist_coeffs
    )
    origin_2d = origin_2d.reshape(-1, 2)[0]
    
    # Проверяем видимость начала
    if not (0 <= origin_2d[0] < w and 0 <= origin_2d[1] < h):
        return frame
    
    origin_2d = (int(origin_2d[0]), int(origin_2d[1]))
    
    # Цвета осей
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # X-синий, Y-зеленый, Z-красный
    labels = ['X', 'Y', 'Z']
    
    for i, direction in enumerate(axes_directions):
        # Проецируем конец оси
        end_point = np.array([direction], dtype=np.float32)
        end_2d, _ = cv2.projectPoints(
            end_point, rvec, tvec, camera_matrix, dist_coeffs
        )
        end_2d = end_2d.reshape(-1, 2)[0]
        
        # Ограничиваем длину для отображения
        end_2d = (int(end_2d[0]), int(end_2d[1]))
        
        # Рисуем ось
        cv2.arrowedLine(frame, origin_2d, end_2d, colors[i], 2, tipLength=0.2)
        
        # Подпись
        label_pos = (end_2d[0] + 5, end_2d[1] - 5)
        cv2.putText(frame, labels[i], label_pos,
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[i], 2)
    
    return frame