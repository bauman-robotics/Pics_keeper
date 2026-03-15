"""
Логирование отладочной информации
"""
import numpy as np
import cv2
from datetime import datetime
import json
from pathlib import Path


class DebugLogger:
    """Логирование отладочной информации об осях и маркерах"""
    
    def __init__(self, config):
        self.enabled = config.get('debug', {}).get('log_axes', False)
        self.log_file = Path(config.get('debug', {}).get('log_file', 'logs/axes_debug.log'))
        
        print(f"\n🔧 DebugLogger initialized:")
        print(f"   Enabled: {self.enabled}")
        print(f"   Log file: {self.log_file}")
        
        if self.enabled:
            # Создаем директорию для логов
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            # Очищаем файл при старте
            with open(self.log_file, 'w') as f:
                f.write(f"=== Axis Debug Log Started at {datetime.now()} ===\n")
                f.write("Format: timestamp | marker_center_x,marker_center_y | "
                       "axis_X_x,axis_X_y | axis_Y_x,axis_Y_y | axis_Z_x,axis_Z_y | "
                       "rvec | tvec\n\n")
            print(f"   Log file created/cleared")
    
    def log_axes_data(self, frame, rvec, tvec, camera_matrix, dist_coeffs, marker_corners=None):
        """Логирование данных об осях и маркере"""
        if not self.enabled:
            return
        
        try:
            h, w = frame.shape[:2]
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Проецируем точки осей
            axis_points = np.float32([
                [0, 0, 0],      # начало
                [0.05, 0, 0],   # X
                [0, 0.05, 0],   # Y
                [0, 0, 0.05]    # Z
            ]).reshape(-1, 3)
            
            img_points, _ = cv2.projectPoints(
                axis_points, rvec, tvec, camera_matrix, dist_coeffs
            )
            img_points = img_points.reshape(-1, 2)
            
            # Получаем центр маркера
            if marker_corners is not None:
                marker_center = np.mean(marker_corners, axis=0)
            else:
                marker_center = img_points[0]
            
            # Формируем строку лога
            log_line = (f"{timestamp} | "
                       f"{marker_center[0]:.1f},{marker_center[1]:.1f} | "
                       f"{img_points[1][0]:.1f},{img_points[1][1]:.1f} | "
                       f"{img_points[2][0]:.1f},{img_points[2][1]:.1f} | "
                       f"{img_points[3][0]:.1f},{img_points[3][1]:.1f} | "
                       f"{rvec[0][0]:.3f},{rvec[1][0]:.3f},{rvec[2][0]:.3f} | "
                       f"{tvec[0][0]:.3f},{tvec[1][0]:.3f},{tvec[2][0]:.3f}\n")
            
            # Записываем в файл
            with open(self.log_file, 'a') as f:
                f.write(log_line)
            
            # Проверяем видимость оси Z
            z_visible = (0 <= img_points[3][0] < w and 0 <= img_points[3][1] < h)
            if not z_visible:
                print(f"⚠️ Axis Z not visible at {timestamp}")
                print(f"   Z endpoint: ({img_points[3][0]:.1f}, {img_points[3][1]:.1f})")
                print(f"   Frame size: {w}x{h}")
                
        except Exception as e:
            print(f"❌ Error logging axes data: {e}")
    
    def analyze_axis_behavior(self):
        """Анализ поведения осей за период логирования"""
        if not self.enabled or not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            # Пропускаем заголовок
            data_lines = [line for line in lines if '|' in line and not line.startswith('===')]
            
            if len(data_lines) < 2:
                print("Not enough data points for analysis")
                return
            
            # Берем последние две записи
            last_line = data_lines[-1].strip().split('|')
            prev_line = data_lines[-2].strip().split('|')
            
            print(f"\n📊 Axis Analysis:")
            print(f"   Last marker center: {last_line[1].strip()}")
            print(f"   Last Z endpoint: {last_line[4].strip()}")
            
            # Анализ движения Z оси
            try:
                last_z = [float(x) for x in last_line[4].strip().split(',')]
                prev_z = [float(x) for x in prev_line[4].strip().split(',')]
                z_dx = last_z[0] - prev_z[0]
                z_dy = last_z[1] - prev_z[1]
                print(f"   Z movement: dx={z_dx:.1f}, dy={z_dy:.1f}")
            except:
                pass
                
        except Exception as e:
            print(f"Error analyzing axes: {e}")


def draw_axes_debug(frame, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Рисование осей с отображением числовых значений для отладки
    """
    h, w = frame.shape[:2]
    
    # Точки для осей
    axis_points = np.float32([
        [0, 0, 0],
        [0.05, 0, 0],
        [0, 0.05, 0],
        [0, 0, 0.05]
    ]).reshape(-1, 3)
    
    # Проекция
    img_points, _ = cv2.projectPoints(
        axis_points, rvec, tvec, camera_matrix, dist_coeffs
    )
    img_points = img_points.reshape(-1, 2)
    
    origin = img_points[0].astype(int)
    
    # Проверяем видимость начала
    if not (0 <= origin[0] < w and 0 <= origin[1] < h):
        cv2.putText(frame, "Marker outside frame", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame
    
    # Рисуем оси с подписями координат
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # BGR: X-синий, Y-зеленый, Z-красный
    
    for i in range(1, 4):
        end = img_points[i].astype(int)
        
        # Рисуем линию
        cv2.line(frame, tuple(origin), tuple(end), colors[i-1], 2)
        
        # Подпись оси
        label = ['X', 'Y', 'Z'][i-1]
        cv2.putText(frame, label, (end[0] + 5, end[1] - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[i-1], 2)
        
        # Координаты конца оси
        coord_text = f"{label}:({end[0]},{end[1]})"
        cv2.putText(frame, coord_text, (10, 50 + (i-1)*20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors[i-1], 1)
    
    # Координаты центра маркера
    cv2.putText(frame, f"Center:({origin[0]},{origin[1]})", (10, 110),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    return frame


def visualize_logged_data(frame, log_data):
    """Визуализация данных из лога на кадре"""
    h, w = frame.shape[:2]
    
    # Рисуем информационную панель
    overlay = frame.copy()
    cv2.rectangle(overlay, (w-300, 10), (w-10, 200), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    y_pos = 30
    cv2.putText(frame, "AXIS DEBUG INFO", (w-280, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    y_pos += 20
    
    # Центр маркера
    mx, my = log_data['marker_center']
    cv2.putText(frame, f"Marker: ({mx:.0f}, {my:.0f})", (w-280, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    y_pos += 20
    
    # Ось Z
    zx, zy = log_data['axis_Z_end']
    color = (0, 255, 0) if log_data.get('axis_Z_visible', True) else (0, 0, 255)
    cv2.putText(frame, f"Z end: ({zx:.0f}, {zy:.0f})", (w-280, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    y_pos += 20
    
    # Расстояние до Z
    dist = np.sqrt((zx - mx)**2 + (zy - my)**2)
    cv2.putText(frame, f"Z length: {dist:.0f} px", (w-280, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    y_pos += 20
    
    # tvec
    if 'tvec' in log_data:
        tx, ty, tz = log_data['tvec']
        cv2.putText(frame, f"tvec: ({tx:.3f}, {ty:.3f}, {tz:.3f})", (w-280, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    return frame