"""
Математические утилиты
"""
import numpy as np
import cv2


def rotation_vector_to_euler(rvec):
    """
    Преобразование вектора поворота в углы Эйлера (roll, pitch, yaw)
    
    Args:
        rvec: вектор поворота (3,1)
        
    Returns:
        roll, pitch, yaw в градусах
    """
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
    """
    Коррекция системы координат AprilTag -> OpenCV
    Финальная версия с правильной осью Z
    """
    R, _ = cv2.Rodrigues(rvec)
    
    # Правильное преобразование:
    # X: оставляем как есть
    # Y: инвертируем (было вверх, стало вниз)
    # Z: инвертируем
    R_flip = np.array([[1,  0,  0],
                       [0, -1,  0],
                       [0,  0, -1]])  
    
    R_corrected = R @ R_flip
    rvec_corrected, _ = cv2.Rodrigues(R_corrected)
    
    return rvec_corrected, tvec
 
def compute_roi_size(pattern_size_mm, distance_m, fx):
    """
    Вычисление размера ROI в пикселях для заданного физического размера
    
    Args:
        pattern_size_mm: физический размер паттерна в мм
        distance_m: расстояние до объекта в метрах
        fx: фокусное расстояние камеры в пикселях
        
    Returns:
        размер ROI в пикселях
    """
    if distance_m < 0.01:
        distance_m = 0.01
    
    pattern_size_m = pattern_size_mm / 1000.0
    projected_px = (pattern_size_m * fx) / distance_m
    
    roi_size = int(projected_px * 4.0)  # margin 4x
    roi_size = max(roi_size, 40)   # минимум 40px
    roi_size = min(roi_size, 300)  # максимум 300px
    
    return roi_size


def normalize_vector(v):
    """Нормализация вектора"""
    norm = np.linalg.norm(v)
    if norm < 1e-9:
        return v
    return v / norm


def angle_between_vectors(v1, v2):
    """Угол между векторами в градусах"""
    v1_norm = normalize_vector(v1)
    v2_norm = normalize_vector(v2)
    
    dot = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
    angle = np.arccos(dot)
    
    return np.degrees(angle)


def project_points_3d_to_2d(points_3d, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Проекция 3D точек на 2D плоскость изображения
    
    Args:
        points_3d: массив точек (N, 3)
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        
    Returns:
        массив 2D точек (N, 2)
    """
    points_2d, _ = cv2.projectPoints(
        points_3d.reshape(-1, 1, 3),
        rvec, tvec,
        camera_matrix,
        dist_coeffs
    )
    return points_2d.reshape(-1, 2)


def create_axes_points(length=0.1):
    """
    Создание точек для осей координат
    
    Args:
        length: длина оси в метрах
        
    Returns:
        (points_3d, lines) - точки и соединения для отрисовки
    """
    # Точки для осей: начало координат и концы осей
    points = np.array([
        [0, 0, 0],           # O - начало
        [length, 0, 0],      # X
        [0, length, 0],      # Y
        [0, 0, length]       # Z
    ], dtype=np.float32)
    
    # Соединения для линий
    lines = [(0, 1), (0, 2), (0, 3)]  # O-X, O-Y, O-Z
    
    return points, lines


def draw_axes(frame, rvec, tvec, camera_matrix, dist_coeffs, length=0.05):
    """
    Рисование осей координат на кадре
    
    Args:
        frame: кадр для отрисовки
        rvec: вектор поворота
        tvec: вектор трансляции
        camera_matrix: матрица камеры
        dist_coeffs: коэффициенты дисторсии
        length: длина оси в метрах
        
    Returns:
        frame с нарисованными осями
    """
    points, lines = create_axes_points(length)
    
    # Проекция точек
    img_points, _ = cv2.projectPoints(
        points, rvec, tvec, camera_matrix, dist_coeffs
    )
    img_points = img_points.reshape(-1, 2).astype(int)
    
    # Цвета осей: X-красный, Y-зеленый, Z-синий
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]
    
    for i, (start_idx, end_idx) in enumerate(lines):
        start_point = tuple(img_points[start_idx])
        end_point = tuple(img_points[end_idx])
        
        # Проверка, что точки в пределах кадра
        if (0 <= start_point[0] < frame.shape[1] and 
            0 <= start_point[1] < frame.shape[0] and
            0 <= end_point[0] < frame.shape[1] and 
            0 <= end_point[1] < frame.shape[0]):
            
            cv2.arrowedLine(frame, start_point, end_point, 
                           colors[i], 2, tipLength=0.2)
            
            # Подписи осей
            cv2.putText(frame, ['X', 'Y', 'Z'][i], 
                       (end_point[0] + 5, end_point[1] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[i], 2)
    
    return frame