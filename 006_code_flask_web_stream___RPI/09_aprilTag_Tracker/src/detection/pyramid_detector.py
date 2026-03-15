"""
Детектирование центров граней пирамиды
"""
import numpy as np
import cv2
from .pyramid_geometry import PyramidGeometry


class PyramidDetector:
    """Детектор центров граней по черным эллипсам"""
    
    def __init__(self, config: dict, geometry: PyramidGeometry):
        self.config = config
        self.geometry = geometry
        self.roi_margin = config['roi_margin']
        self.reproj_threshold = config['reproj_threshold']
        self.debug = False  # будет установлено из основного конфига
    
    def detect(self, gray_frame, rvec, tvec, camera_matrix, dist_coeffs):
        """
        Детектирование центров граней
        
        Returns:
            results - список результатов для каждой грани
            Если debug=True, также возвращает debug_frame
        """
        results = []
        h, w = gray_frame.shape[:2]
        
        # Получаем все грани
        face_names = self.geometry.get_all_faces()
        
        if self.debug:
            debug_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)
            print(f"\n{'='*60}")
            print(f"🔍 PYRAMID DETECTION")
            print(f"{'='*60}")
        
        for face_name in face_names:
            # Проверка видимости
            visible, dot = self.geometry.is_face_visible(face_name, rvec, tvec)
            
            # Базовый результат
            result = {
                'face': face_name,
                'center_3d': self.geometry.get_face_center_3d(face_name),
                'center_2d': None,
                'proj_center': None,
                'reproj_err': None,
                'visible': visible,
                'confidence': 0.0
            }
            
            if not visible:
                if self.debug:
                    print(f"   ⏭️ {face_name}: not visible")
                results.append(result)
                continue
            
            # Проекция центра грани
            center_3d = result['center_3d'].reshape(1, 1, 3).astype(np.float32)
            proj, _ = cv2.projectPoints(center_3d, rvec, tvec, camera_matrix, dist_coeffs)
            center_proj = proj[0][0]
            result['proj_center'] = center_proj
            
            # Проекция вершин грани
            vertices_3d = self.geometry.get_face_vertices_3d(face_name)
            vertices_2d, _ = cv2.projectPoints(
                vertices_3d, rvec, tvec, camera_matrix, dist_coeffs
            )
            vertices_2d = vertices_2d.reshape(-1, 2)
            
            # Вычисление ROI
            roi_coords = self._compute_roi(vertices_2d, w, h)
            if roi_coords is None:
                results.append(result)
                continue
            
            x1, y1, x2, y2 = roi_coords
            
            if self.debug:
                self._draw_debug(debug_frame, face_name, vertices_2d, 
                                center_proj, roi_coords)
            
            # Детекция эллипса в ROI
            roi = gray_frame[y1:y2, x1:x2]
            ellipse = self._detect_ellipse(roi)
            
            if ellipse:
                center, axes, angle, confidence = ellipse
                
                # Перевод в глобальные координаты
                found_center = center + np.array([x1, y1])
                reproj_err = float(np.linalg.norm(found_center - center_proj))
                
                result['center_2d'] = found_center
                result['reproj_err'] = reproj_err
                result['confidence'] = confidence
                
                if self.debug:
                    self._draw_ellipse(debug_frame, found_center, axes, 
                                      angle, confidence, reproj_err)
            
            results.append(result)
        
        if self.debug:
            return results, debug_frame
        
        return results
    
    def _compute_roi(self, vertices_2d, frame_w, frame_h):
        """Вычисление ROI по вершинам грани"""
        x_coords = vertices_2d[:, 0]
        y_coords = vertices_2d[:, 1]
        
        x1 = max(0, int(np.min(x_coords)))
        y1 = max(0, int(np.min(y_coords)))
        x2 = min(frame_w, int(np.max(x_coords)))
        y2 = min(frame_h, int(np.max(y_coords)))
        
        # Проверка минимального размера
        if x2 - x1 < 20 or y2 - y1 < 20:
            return None
        
        return (x1, y1, x2, y2)
    
    def _detect_ellipse(self, roi):
        """
        Детектирование черного эллипса на белом фоне
        """
        if roi.size == 0:
            return None
        
        h, w = roi.shape
        roi_center = np.array([w/2, h/2])
        max_dist = min(h, w) * 0.4
        
        # Бинаризация
        _, binary = cv2.threshold(roi, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Морфологические операции
        kernel = np.ones((3,3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Поиск контуров
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, 
                                       cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            return None
        
        best_ellipse = None
        best_confidence = 0.0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Фильтр по площади
            roi_area = h * w
            if area < roi_area * 0.05 or area > roi_area * 0.4:
                continue
            
            if len(contour) >= 5:
                ellipse = cv2.fitEllipse(contour)
                center = ellipse[0]
                axes = ellipse[1]
                angle = ellipse[2]
                
                # Проверка расстояния от центра
                dist = np.linalg.norm(center - roi_center)
                if dist > max_dist:
                    continue
                
                # Проверка, что эллипс не касается границ
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.ellipse(mask, 
                           (int(center[0]), int(center[1])),
                           (int(axes[0]/2), int(axes[1]/2)),
                           angle, 0, 360, 255, -1)
                
                border_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(border_mask, (0,0), (w-1,h-1), 255, 1)
                
                ellipse_border = cv2.bitwise_and(mask, border_mask)
                if cv2.countNonZero(ellipse_border) > 0:
                    continue
                
                # Оценка качества
                ellipse_area = np.pi * (axes[0]/2) * (axes[1]/2)
                area_ratio = area / ellipse_area
                
                if 0.7 < area_ratio < 1.3:
                    confidence = min(1.0, area_ratio)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_ellipse = (center, axes, angle, confidence)
        
        return best_ellipse
    
    def draw_results(self, frame, results, rvec, tvec, camera_matrix, dist_coeffs):
        """Отрисовка результатов детектирования"""
        face_colors = {
            'FRONT': (0, 255, 255),   # желтый
            'BACK': (255, 0, 255),    # розовый
            'LEFT': (255, 255, 0),    # голубой
            'RIGHT': (255, 128, 0)    # оранжевый
        }
        
        # Рисуем ребра пирамиды
        self._draw_pyramid_edges(frame, rvec, tvec, camera_matrix, dist_coeffs)
        
        for r in results:
            if not isinstance(r, dict):
                continue
            
            name = r.get('face', 'UNKNOWN')
            color = face_colors.get(name, (200, 200, 200))
            
            # Проекция центра
            if 'proj_center' in r and r['proj_center'] is not None:
                px, py = int(r['proj_center'][0]), int(r['proj_center'][1])
                if 0 <= px < frame.shape[1] and 0 <= py < frame.shape[0]:
                    cv2.circle(frame, (px, py), 6, color, 1)
                    cv2.drawMarker(frame, (px, py), color,
                                  cv2.MARKER_CROSS, 12, 1)
            
            # Найденный центр
            if 'center_2d' in r and r['center_2d'] is not None:
                cx, cy = int(r['center_2d'][0]), int(r['center_2d'][1])
                if 0 <= cx < frame.shape[1] and 0 <= cy < frame.shape[0]:
                    cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)
                    cv2.circle(frame, (cx, cy), 10, (255, 255, 255), 1)
                    
                    # Ошибка и уверенность
                    info = []
                    if 'reproj_err' in r:
                        info.append(f"err:{r['reproj_err']:.1f}")
                    if 'confidence' in r:
                        info.append(f"conf:{r['confidence']:.2f}")
                    
                    if info:
                        cv2.putText(frame, " ".join(info), 
                                   (cx+15, cy-15), cv2.FONT_HERSHEY_SIMPLEX,
                                   0.4, (255, 255, 255), 1)
                    
                    cv2.putText(frame, name, (cx-20, cy-25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return frame
    
    def _draw_pyramid_edges(self, frame, rvec, tvec, camera_matrix, dist_coeffs):
        """Отрисовка ребер пирамиды"""
        # Объединяем вершины
        all_vertices = np.vstack([
            self.geometry.top_vertices,
            self.geometry.bottom_vertices
        ])
        
        # Проецируем
        vertices_2d, _ = cv2.projectPoints(
            all_vertices, rvec, tvec, camera_matrix, dist_coeffs
        )
        vertices_2d = vertices_2d.reshape(-1, 2)
        
        # Верхняя грань
        for i in range(4):
            pt1 = vertices_2d[i]
            pt2 = vertices_2d[(i+1)%4]
            cv2.line(frame, (int(pt1[0]), int(pt1[1])),
                    (int(pt2[0]), int(pt2[1])), (0, 255, 255), 2)
        
        # Нижняя грань
        for i in range(4, 8):
            pt1 = vertices_2d[i]
            pt2 = vertices_2d[4 + (i+1)%4]
            cv2.line(frame, (int(pt1[0]), int(pt1[1])),
                    (int(pt2[0]), int(pt2[1])), (255, 0, 255), 2)
        
        # Боковые ребра
        for i in range(4):
            pt1 = vertices_2d[i]
            pt2 = vertices_2d[i+4]
            cv2.line(frame, (int(pt1[0]), int(pt1[1])),
                    (int(pt2[0]), int(pt2[1])), (255, 255, 0), 2)
    
    def _draw_debug(self, frame, face_name, vertices_2d, center_proj, roi_coords):
        """Отладочная отрисовка"""
        colors = {
            'FRONT': (0, 255, 255),
            'BACK': (255, 0, 255),
            'LEFT': (255, 255, 0),
            'RIGHT': (255, 128, 0)
        }
        color = colors.get(face_name, (0, 255, 0))
        
        # Вершины грани
        for i, pt in enumerate(vertices_2d):
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 3, color, -1)
        
        # ROI
        x1, y1, x2, y2 = roi_coords
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
        cv2.putText(frame, face_name, (x1, y1-5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    def _draw_ellipse(self, frame, center, axes, angle, confidence, reproj_err):
        """Отрисовка детектированного эллипса"""
        # Контур эллипса
        cv2.ellipse(frame, 
                   (int(center[0]), int(center[1])),
                   (int(axes[0]/2), int(axes[1]/2)),
                   angle, 0, 360, (0, 255, 0), 1)
        
        # Центр
        cv2.circle(frame, (int(center[0]), int(center[1])), 3, (0, 255, 0), -1)
        
        # Оси
        angle_rad = np.radians(angle)
        dx = int(axes[0]/2 * np.cos(angle_rad))
        dy = int(axes[0]/2 * np.sin(angle_rad))
        cv2.line(frame,
                (int(center[0]) - dx, int(center[1]) - dy),
                (int(center[0]) + dx, int(center[1]) + dy),
                (0, 255, 0), 1)
