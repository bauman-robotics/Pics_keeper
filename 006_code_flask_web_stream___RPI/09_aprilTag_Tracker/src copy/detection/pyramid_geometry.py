"""
Геометрия усеченной пирамиды
"""
import numpy as np
import cv2


class PyramidGeometry:
    """Вычисление геометрии пирамиды"""
    
    def __init__(self, config: dict):
        self.base_size = config['base_size_mm']
        self.top_size = config['top_size_mm']
        self.angle_deg = config['angle_deg']
        self.line_width = config['line_width_mm']
        
        self._compute_geometry()
    
    def _compute_geometry(self):
        """Вычисление всех геометрических параметров"""
        angle_rad = np.radians(self.angle_deg)
        top_half = self.top_size / 2.0
        base_half = self.base_size / 2.0
        
        # Высота пирамиды
        self.height = (base_half - top_half) * np.tan(angle_rad)
        
        # Вершины граней
        self.faces_vertices = self._compute_faces_vertices(top_half, base_half, self.height)
        
        # Центры граней
        self.face_centers = self._compute_face_centers()
        
        # Нормали граней
        self.face_normals = self._compute_face_normals(angle_rad)
        
        # Вершины для отрисовки ребер
        self._compute_edge_vertices(top_half, base_half, self.height)
    
    def _compute_faces_vertices(self, top_half, base_half, height):
        """Вычисление вершин всех граней"""
        h_display = -height  # для отображения под маркером
        
        return {
            'FRONT': np.array([
                [-top_half, -top_half, 0.0],
                [ top_half, -top_half, 0.0],
                [ base_half, -base_half, h_display],
                [-base_half, -base_half, h_display]
            ], dtype=np.float32),
            
            'BACK': np.array([
                [ top_half, top_half, 0.0],
                [-top_half, top_half, 0.0],
                [-base_half, base_half, h_display],
                [ base_half, base_half, h_display]
            ], dtype=np.float32),
            
            'LEFT': np.array([
                [-top_half, -top_half, 0.0],
                [-top_half, top_half, 0.0],
                [-base_half, base_half, h_display],
                [-base_half, -base_half, h_display]
            ], dtype=np.float32),
            
            'RIGHT': np.array([
                [ top_half, top_half, 0.0],
                [ top_half, -top_half, 0.0],
                [ base_half, -base_half, h_display],
                [ base_half, base_half, h_display]
            ], dtype=np.float32)
        }
    
    def _compute_face_centers(self):
        """Вычисление центров граней"""
        centers = {}
        for name, vertices in self.faces_vertices.items():
            centers[name] = np.mean(vertices, axis=0)
        return centers
    
    def _compute_face_normals(self, angle_rad):
        """Вычисление нормалей граней с учетом наклона"""
        sin_a = np.sin(angle_rad)
        cos_a = np.cos(angle_rad)
        
        return {
            'FRONT': np.array([0.0, -cos_a, sin_a]),
            'BACK':  np.array([0.0,  cos_a, sin_a]),
            'LEFT':  np.array([-cos_a, 0.0, sin_a]),
            'RIGHT': np.array([ cos_a, 0.0, sin_a])
        }
    
    def _compute_edge_vertices(self, top_half, base_half, height):
        """Вычисление вершин для отрисовки ребер"""
        h_display = -height
        
        # Верхняя грань (с маркером)
        self.top_vertices = np.array([
            [-top_half, -top_half, 0.0],
            [ top_half, -top_half, 0.0],
            [ top_half,  top_half, 0.0],
            [-top_half,  top_half, 0.0]
        ], dtype=np.float32)
        
        # Нижняя грань (основание)
        self.bottom_vertices = np.array([
            [-base_half, -base_half, h_display],
            [ base_half, -base_half, h_display],
            [ base_half,  base_half, h_display],
            [-base_half,  base_half, h_display]
        ], dtype=np.float32)
    
    def get_face_vertices_3d(self, face_name):
        """Получить вершины грани в 3D"""
        return self.faces_vertices.get(face_name, np.array([]))
    
    def get_face_center_3d(self, face_name):
        """Получить центр грани в 3D"""
        return self.face_centers.get(face_name, np.array([0, 0, 0]))
    
    def get_face_normal(self, face_name):
        """Получить нормаль грани"""
        return self.face_normals.get(face_name, np.array([0, 0, 1]))
    
    def is_face_visible(self, face_name, rvec, tvec):
        """Проверка видимости грани"""
        normal = self.get_face_normal(face_name)
        R, _ = cv2.Rodrigues(rvec)
        normal_cam = R @ normal
        vec_to_cam = -tvec.flatten() / (np.linalg.norm(tvec) + 1e-9)
        dot = float(np.dot(normal_cam, vec_to_cam))
        return dot > 0.0, dot
    
    def get_all_faces(self):
        """Получить список всех граней"""
        return list(self.faces_vertices.keys())
