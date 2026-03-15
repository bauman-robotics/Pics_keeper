"""
Загрузка и работа с 3D моделью в формате OBJ
"""
import numpy as np
import os
from pathlib import Path


class OBJModel:
    """Загрузчик и обработчик OBJ моделей"""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.vertices = []
        self.faces = []
        self.edges = set()
        
        self.load_obj(filename)
        self._compute_edges()
        self._compute_statistics()
    
    def load_obj(self, filename: str):
        """Загрузка OBJ файла"""
        filepath = Path(filename)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filename}")
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split()
                    if not parts:
                        continue
                    
                    if parts[0] == 'v':
                        # Вершина
                        self.vertices.append([
                            float(parts[1]) / 1000.0,  # мм → м
                            float(parts[2]) / 1000.0,
                            float(parts[3]) / 1000.0
                        ])
                    
                    elif parts[0] == 'f':
                        # Грань
                        face = []
                        for part in parts[1:]:
                            idx = part.split('/')[0]
                            if idx:
                                face.append(int(idx) - 1)
                        if len(face) >= 3:
                            self.faces.append(face)
            
            self.vertices = np.array(self.vertices, dtype=np.float32)
            
        except Exception as e:
            raise RuntimeError(f"Error loading OBJ file: {e}")
    
    def _compute_edges(self):
        """Вычисление всех ребер модели"""
        for face in self.faces:
            for i in range(len(face)):
                edge = tuple(sorted((face[i], face[(i+1) % len(face)])))
                self.edges.add(edge)
        self.edges = list(self.edges)
    
    def _compute_statistics(self):
        """Вычисление статистики модели"""
        if len(self.vertices) == 0:
            self.min_bounds = np.zeros(3)
            self.max_bounds = np.zeros(3)
            self.center = np.zeros(3)
            self.size = np.zeros(3)
            self.diagonal = 0
            return
        
        self.min_bounds = np.min(self.vertices, axis=0)
        self.max_bounds = np.max(self.vertices, axis=0)
        self.center = (self.min_bounds + self.max_bounds) / 2
        self.size = self.max_bounds - self.min_bounds
        self.diagonal = np.linalg.norm(self.size)
    
    def get_default_position(self):
        """Получение позиции модели по умолчанию"""
        return {
            'scale': 0.001,
            'rot_x': 0.0,
            'rot_y': 0.0,
            'rot_z': 0.0,
            'offset_x': 0.0,
            'offset_y': 0.0,
            'offset_z': 0.0,
            'mode': 1
        }
    
    def get_transform_matrix(self, scale, rot_x, rot_y, rot_z,
                            offset_x, offset_y, offset_z):
        """
        Получение матрицы трансформации
        
        Порядок: scale -> rot_z -> rot_y -> rot_x -> translate
        """
        S = np.diag([scale, scale, scale, 1.0])
        
        # Матрицы поворота
        Rx = np.eye(4)
        Ry = np.eye(4)
        Rz = np.eye(4)
        
        if rot_x != 0:
            rad = np.radians(rot_x)
            Rx[:3, :3] = [[1, 0, 0],
                          [0, np.cos(rad), -np.sin(rad)],
                          [0, np.sin(rad), np.cos(rad)]]
        
        if rot_y != 0:
            rad = np.radians(rot_y)
            Ry[:3, :3] = [[np.cos(rad), 0, np.sin(rad)],
                          [0, 1, 0],
                          [-np.sin(rad), 0, np.cos(rad)]]
        
        if rot_z != 0:
            rad = np.radians(rot_z)
            Rz[:3, :3] = [[np.cos(rad), -np.sin(rad), 0],
                          [np.sin(rad), np.cos(rad), 0],
                          [0, 0, 1]]
        
        # Комбинируем повороты: Z -> Y -> X
        R = Rx @ Ry @ Rz
        
        # Матрица трансляции
        T = np.eye(4)
        T[:3, 3] = [offset_x, offset_y, offset_z]
        
        return T @ R @ S
    
    def transform(self, transform_matrix):
        """
        Применение матрицы трансформации к вершинам
        
        Args:
            transform_matrix: 4x4 матрица трансформации
            
        Returns:
            Трансформированные вершины (N, 3)
        """
        if len(self.vertices) == 0:
            return None
        
        vertices_h = np.hstack([
            self.vertices,
            np.ones((len(self.vertices), 1))
        ])
        
        transformed_h = (transform_matrix @ vertices_h.T).T
        return transformed_h[:, :3]
    
    def get_edges(self):
        """Получение списка ребер"""
        return self.edges
    
    def print_statistics(self):
        """Вывод статистики модели"""
        print(f"\n{'='*60}")
        print(f"📊 MODEL STATS: {os.path.basename(self.filename)}")
        print(f"{'='*60}")
        print(f"✅ Loaded: {len(self.vertices)} vertices, {len(self.faces)} faces")
        print(f"\n📐 BOUNDS (meters):")
        print(f"   Min: ({self.min_bounds[0]:.4f}, {self.min_bounds[1]:.4f}, "
              f"{self.min_bounds[2]:.4f})")
        print(f"   Max: ({self.max_bounds[0]:.4f}, {self.max_bounds[1]:.4f}, "
              f"{self.max_bounds[2]:.4f})")
        print(f"   Size (WxHxD): {self.size[0]:.4f} x {self.size[1]:.4f} x "
              f"{self.size[2]:.4f}")
        print(f"   Diagonal: {self.diagonal:.4f} m")
        print(f"{'='=}60")
