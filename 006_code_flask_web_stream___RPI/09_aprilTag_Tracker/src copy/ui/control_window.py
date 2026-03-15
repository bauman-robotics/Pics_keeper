"""
Окно управления с трекбарами
"""
import cv2
import numpy as np


class ControlWindow:
    """Окно с ползунками для настройки параметров"""
    
    def __init__(self, config):
        self.config = config
        self.window_name = 'Controls'
        
        # Параметры трекбаров
        self.trackbars = {
            'Scale_coarse': {'range': (0, 100), 'default': 50},
            'Rot X_coarse': {'range': (0, 360), 'default': 180},
            'Rot Y_coarse': {'range': (0, 360), 'default': 180},
            'Rot Z_coarse': {'range': (0, 360), 'default': 180},
            'Offset X_coarse': {'range': (0, 1000), 'default': 500},
            'Offset Y_coarse': {'range': (0, 1000), 'default': 500},
            'Offset Z_coarse': {'range': (0, 1000), 'default': 500},
            'Scale_fine': {'range': (0, 1000), 'default': 500},
            'Rot X_fine': {'range': (0, 1000), 'default': 500},
            'Rot Y_fine': {'range': (0, 1000), 'default': 500},
            'Rot Z_fine': {'range': (0, 1000), 'default': 500},
            'Offset X_fine': {'range': (0, 1000), 'default': 500},
            'Offset Y_fine': {'range': (0, 1000), 'default': 500},
            'Offset Z_fine': {'range': (0, 1000), 'default': 500},
            'Mode': {'range': (0, 2), 'default': 1}
        }
        
        self._create_window()
    
    def _create_window(self):
        """Создание окна и трекбаров"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 500, 700)
        
        def nothing(x):
            pass
        
        for name, params in self.trackbars.items():
            cv2.createTrackbar(
                name,
                self.window_name,
                params['default'],
                params['range'][1],
                nothing
            )
    
    def get_all_values(self):
        """Получение всех значений трекбаров"""
        values = {}
        for name in self.trackbars.keys():
            values[name] = cv2.getTrackbarPos(name, self.window_name)
        return values
    
    def set_value(self, name, value):
        """Установка значения трекбара"""
        if name in self.trackbars:
            cv2.setTrackbarPos(name, self.window_name, value)
    
    def set_all_values(self, values):
        """Установка всех значений трекбаров"""
        for name, value in values.items():
            if name in self.trackbars:
                self.set_value(name, value)
    
    def reset_sliders(self):
        """Сброс всех трекбаров к значениям по умолчанию"""
        for name, params in self.trackbars.items():
            self.set_value(name, params['default'])
    
    def update(self, marker_detected, video_only, refine_active,
              n_pyramid_found, refine_reproj_info):
        """Обновление информации в окне управления"""
        # Создаем информационное окно
        info_frame = np.zeros((700, 500, 3), dtype=np.uint8)
        
        y_pos = 30
        line_height = 25
        
        # Заголовок
        cv2.putText(info_frame, "CONTROL PANEL", (20, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_pos += 40
        
        # Режимы
        cv2.putText(info_frame, f"VIDEO ONLY: {'ACTIVE' if video_only else 'OFF'}",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                   (0, 255, 0) if video_only else (100, 100, 100), 1)
        y_pos += line_height
        
        cv2.putText(info_frame, f"REFINE: {'ACTIVE' if refine_active else 'OFF'}",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                   (0, 220, 255) if refine_active else (100, 100, 100), 1)
        y_pos += line_height * 2
        
        # Статус маркера
        cv2.putText(info_frame, f"Target ID: {self.config['apriltag']['target_id']}",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                   (255, 255, 0), 1)
        y_pos += line_height
        
        marker_color = (0, 255, 0) if marker_detected else (0, 0, 255)
        cv2.putText(info_frame, f"Detected: {'YES' if marker_detected else 'NO'}",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                   marker_color, 1)
        y_pos += line_height * 2
        
        # Информация о пирамиде
        if refine_active:
            cv2.putText(info_frame, f"Line crosses found: {n_pyramid_found}/4",
                       (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                       (200, 200, 200), 1)
            y_pos += line_height
            
            rb, ra = refine_reproj_info
            if rb is not None:
                if ra is not None:
                    cv2.putText(info_frame,
                               f"Reproj: {rb:.2f}px -> {ra:.2f}px",
                               (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                               (200, 200, 200), 1)
                else:
                    cv2.putText(info_frame,
                               f"Reproj before: {rb:.2f}px",
                               (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                               (200, 200, 200), 1)
                y_pos += line_height * 2
        
        # Текущие тонкие настройки
        values = self.get_all_values()
        
        cv2.putText(info_frame, "Current fine values:", (20, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_pos += line_height
        
        scale_fine = (values['Scale_fine'] - 500) / 500 * 10
        cv2.putText(info_frame,
                   f"Scale fine: {scale_fine:+.1f}%",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                   (200, 200, 200), 1)
        y_pos += line_height
        
        rot_x = (values['Rot X_fine'] - 500) / 100 * 5
        rot_y = (values['Rot Y_fine'] - 500) / 100 * 5
        rot_z = (values['Rot Z_fine'] - 500) / 100 * 5
        cv2.putText(info_frame,
                   f"Rot fine: X{rot_x:+5.2f} Y{rot_y:+5.2f} Z{rot_z:+5.2f} deg",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                   (200, 200, 200), 1)
        y_pos += line_height
        
        off_x = (values['Offset X_fine'] - 500) / 500 * 0.05
        off_y = (values['Offset Y_fine'] - 500) / 500 * 0.05
        off_z = (values['Offset Z_fine'] - 500) / 500 * 0.05
        cv2.putText(info_frame,
                   f"Offset fine: X{off_x:+6.3f} Y{off_y:+6.3f} Z{off_z:+6.3f}m",
                   (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                   (200, 200, 200), 1)
        
        # Отображение
        cv2.imshow(self.window_name, info_frame)
