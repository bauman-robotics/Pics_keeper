"""
Класс для визуальной отладки и логирования
"""
import cv2
import numpy as np
from datetime import datetime


class VisualDebugger:
    """Отладчик для визуализации осей, плоскостей и логирования"""
    
    def __init__(self, config):
        self.config = config
        self.debug_config = config.get('debug', {})
    
    def print_console_debug(self, camera, target_rvec, target_tvec, target_corners):
        """Вывод отладочной информации в консоль"""
        if not self.debug_config.get('verbose', False):
            return
        
        print("\n=== CAMERA MATRIX DEBUG ===")
        print(f"Camera matrix:\n{camera.camera_matrix}")
        print(f"dist_coeffs: {camera.dist_coeffs}")
        print(f"Image size: {camera.width}x{camera.height}")
        
        # Проверяем проекцию центра маркера
        center_3d = np.array([[0, 0, 0]], dtype=np.float32)
        center_2d, _ = cv2.projectPoints(
            center_3d, target_rvec, target_tvec,
            camera.camera_matrix, camera.dist_coeffs
        )
        center_2d = center_2d[0][0]
        print(f"Projected center: ({center_2d[0]:.1f}, {center_2d[1]:.1f})")
        
        # Проецируем все три оси для отладки
        axis_points = np.array([
            [0, 0, 0],      # центр
            [0.05, 0, 0],   # X
            [0, 0.05, 0],   # Y
            [0, 0, 0.05]    # Z
        ], dtype=np.float32)
        
        img_points, _ = cv2.projectPoints(
            axis_points, target_rvec, target_tvec,
            camera.camera_matrix, camera.dist_coeffs
        )
        img_points = img_points.reshape(-1, 2)
        
        print(f"X axis end: ({img_points[1][0]:.1f}, {img_points[1][1]:.1f})")
        print(f"Y axis end: ({img_points[2][0]:.1f}, {img_points[2][1]:.1f})")
        print(f"Z axis end: ({img_points[3][0]:.1f}, {img_points[3][1]:.1f})")
        
        # Проверяем матрицу поворота
        R, _ = cv2.Rodrigues(target_rvec)
        print(f"Rotation matrix:\n{R}")
        print(f"X axis direction (in camera coord): {R[:,0]}")
        print(f"Y axis direction (in camera coord): {R[:,1]}")
        print(f"Z axis direction (in camera coord): {R[:,2]}")
        
        # Проверяем tvec
        print(f"tvec: {target_tvec.flatten()}")
        
        # Проверка угла между нормалью и осью Z
        z_axis = R[:, 2]
        normal_in_camera = R @ np.array([0, 0, 1])
        z_axis = z_axis / np.linalg.norm(z_axis)
        normal_in_camera = normal_in_camera / np.linalg.norm(normal_in_camera)
        dot_product = np.abs(np.dot(z_axis, normal_in_camera))
        angle = np.degrees(np.arccos(np.clip(dot_product, -1.0, 1.0)))
        print(f"Angle between Z axis and normal: {angle:.1f} degrees")
    
    def draw_axes(self, frame, img_points):
        """Отрисовка осей координат"""
        center = img_points[0]
        x_end = img_points[1]
        y_end = img_points[2]
        z_end = img_points[3]
        
        # Рисуем оси
        cv2.arrowedLine(frame, tuple(center), tuple(x_end), (255, 0, 0), 2, tipLength=0.2)  # X - синий
        cv2.arrowedLine(frame, tuple(center), tuple(y_end), (0, 255, 0), 2, tipLength=0.2)  # Y - зеленый
        cv2.arrowedLine(frame, tuple(center), tuple(z_end), (0, 0, 255), 2, tipLength=0.2)  # Z - красный
        
        return x_end, y_end, z_end
    
    def draw_debug_text(self, frame, center, x_end, y_end, z_end):
        """Отрисовка отладочного текста на кадре"""
        if not self.debug_config.get('debug_text', False):
            return
        
        # Подписи осей
        cv2.putText(frame, "X", (x_end[0]+5, x_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(frame, "Y", (y_end[0]+5, y_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(frame, "Z", (z_end[0]+5, z_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Координаты на экране
        cv2.putText(frame, f"Center: ({center[0]}, {center[1]})", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"X: ({x_end[0]}, {x_end[1]})", (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Y: ({y_end[0]}, {y_end[1]})", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(frame, f"Z: ({z_end[0]}, {z_end[1]})", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    def draw_marker_plane(self, frame, target_rvec, target_tvec, camera_matrix, dist_coeffs):
        """Отрисовка плоскости маркера"""
        if not self.debug_config.get('debug_text', False):
            return None
        
        marker_3d = np.array([
            [-0.025, -0.025, 0], [0.025, -0.025, 0],
            [0.025,  0.025, 0], [-0.025,  0.025, 0]
        ], dtype=np.float32)
        
        marker_2d, _ = cv2.projectPoints(
            marker_3d, target_rvec, target_tvec,
            camera_matrix, dist_coeffs
        )
        marker_2d = marker_2d.reshape(-1, 2).astype(int)
        
        cv2.polylines(frame, [marker_2d], True, (255, 255, 0), 1)
        
        return marker_2d.mean(axis=0).astype(int)
    
    def draw_normal(self, frame, center_point, z_end):
        """Отрисовка нормали к плоскости"""
        cv2.line(frame, tuple(center_point), tuple(z_end), (255, 255, 255), 2)
        
        if self.debug_config.get('debug_text', False):
            cv2.putText(frame, "NORMAL", (z_end[0]+5, z_end[1]-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.drawMarker(frame, tuple(z_end), (255, 255, 255), cv2.MARKER_CROSS, 10, 2)
    
    def log_axes_data(self, target_rvec, target_tvec, target_corners, img_points):
        """Логирование данных осей в файл"""
        if not self.debug_config.get('log_axes', False):
            return
        
        marker_center = np.mean(target_corners, axis=0)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        log_line = (f"{timestamp} | "
                   f"{marker_center[0]:.1f},{marker_center[1]:.1f} | "
                   f"{img_points[1][0]:.1f},{img_points[1][1]:.1f} | "
                   f"{img_points[2][0]:.1f},{img_points[2][1]:.1f} | "
                   f"{img_points[3][0]:.1f},{img_points[3][1]:.1f} | "
                   f"{target_rvec[0][0]:.3f},{target_rvec[1][0]:.3f},{target_rvec[2][0]:.3f} | "
                   f"{target_tvec[0][0]:.3f},{target_tvec[1][0]:.3f},{target_tvec[2][0]:.3f}\n")
        
        with open('logs/axes_debug.log', 'a') as f:
            f.write(log_line)
    
    def get_axis_projections(self, target_rvec, target_tvec, camera_matrix, dist_coeffs):
        """Получение проекций осей"""
        axis_points = np.array([
            [0, 0, 0], [0.05, 0, 0], [0, 0.05, 0], [0, 0, 0.05]
        ], dtype=np.float32)
        
        img_points, _ = cv2.projectPoints(
            axis_points, target_rvec, target_tvec,
            camera_matrix, dist_coeffs
        )
        return img_points.reshape(-1, 2).astype(int)
