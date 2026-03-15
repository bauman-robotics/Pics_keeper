#!/usr/bin/env python3
"""
AprilTag 3D Model Viewer - Главный файл приложения
"""
import cv2
import sys
import time
import signal
import numpy as np
from pathlib import Path
from datetime import datetime

# Добавляем родительскую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import ConfigManager
from src.camera.factory import CameraFactory
from src.detection.apriltag_detector import AprilTagDetector
from src.detection.pyramid_geometry import PyramidGeometry
from src.detection.pyramid_detector import PyramidDetector
from src.detection.pose_refiner import PoseRefiner
from src.model.obj_loader import OBJModel
from src.ui.control_window import ControlWindow
from src.ui.display import DisplayManager
from src.ui.button_manager import ButtonManager
from src.ui.info_overlay import InfoOverlay
from src.utils.logger import setup_logger
from src.utils.math_utils import flip_z_axis, rotation_vector_to_euler
from src.utils.debug_logger import DebugLogger, draw_axes_debug

class AprilTagTracker:
    """Основной класс приложения"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        # Загрузка конфигурации
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # Настройка логирования
        self.logger = setup_logger(self.config.get('logging', {}))
        self.logger.info("🚀 Starting AprilTag Tracker")
        
        # Инициализация отладочного логгера
        self.debug_logger = DebugLogger(self.config)


        # Инициализация компонентов
        self._init_camera()
        self._init_detectors()
        self._init_model()
        self._init_ui()
        
        # Переменные состояния
        self.marker_detected = False
        self.last_known_rvec = None
        self.last_known_tvec = None
        self.last_apriltag_corners = None
        self.auto_center_requested = False
        self.pyramid_results_cache = []
        self.n_pyramid_found = 0
        self.refine_reproj_info = (None, None)
        
        # FPS счетчик
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0
        
        # Флаг работы
        self.running = True
        
        # Обработчик сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _init_camera(self):
        """Инициализация камеры"""
        camera_config = self.config['camera']
        self.camera = CameraFactory.create_camera(
            camera_config['type'],
            camera_config
        )
        
        if not self.camera.initialize():
            self.logger.error("❌ Failed to initialize camera")
            sys.exit(1)
        
        # Загрузка калибровки
        self.camera.load_calibration(camera_config['calibration'])
        
        self.logger.info(f"✅ Camera initialized: {self.camera.width}x{self.camera.height}")
    
    def _init_detectors(self):
        """Инициализация детекторов"""
        # AprilTag детектор
        self.apriltag_detector = AprilTagDetector(self.config['apriltag'])
        
        # Геометрия пирамиды
        self.pyramid_geo = PyramidGeometry(self.config['pyramid'])
        
        # Детектор пирамиды
        self.pyramid_detector = PyramidDetector(
            self.config['pyramid'],
            self.pyramid_geo
        )
        
        # Уточнение позы
        self.pose_refiner = PoseRefiner(self.config['pyramid'])
        
        self.logger.info("✅ Detectors initialized")
    
    def _init_model(self):
        """Инициализация 3D модели"""
        model_path = Path(self.config['model']['path'])
        if not model_path.exists():
            self.logger.error(f"❌ Model file not found: {model_path}")
            sys.exit(1)
            
        self.model = OBJModel(str(model_path))
        
        # Загрузка позиции модели
        model_config = self.config_manager.load_model_position()
        if model_config:
            self.model_position = model_config
        else:
            self.model_position = self.model.get_default_position()
        
        self.logger.info(f"✅ Model loaded: {len(self.model.vertices)} vertices")
    
    def _init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Менеджер отображения
        self.display = DisplayManager(self.config['display'])
        
        # Окно управления
        self.control_window = ControlWindow(self.config)
        
        # Менеджер кнопок
        self.button_manager = ButtonManager(
            self.config['ui'],
            self.camera.width,
            self.camera.height
        )
        
        # Информационный оверлей
        self.info_overlay = InfoOverlay(self.config['display'])
        self.info_overlay.target_id = self.config['apriltag']['target_id']  # Устанавливаем ID
        
        # Настройка callback для мыши
        cv2.setMouseCallback(
            self.display.window_name,
            self._mouse_callback,
            {
                'button_manager': self.button_manager,
                'scale_x': 1.0,
                'scale_y': 1.0,
                'offset_x': 0,
                'offset_y': 0
            }
        )
        
        self.logger.info("✅ UI initialized")
    
    def _signal_handler(self, sig, frame):
        """Обработчик сигналов (Ctrl+C)"""
        self.logger.info("\n👋 Interrupted by user")
        self.running = False
    
    def _mouse_callback(self, event, x, y, flags, param):
        """Callback для обработки мыши"""
        # Конвертируем координаты
        orig_x = int((x - param['offset_x']) / param['scale_x'])
        orig_y = int((y - param['offset_y']) / param['scale_y'])
        
        # Проверяем границы кадра
        if orig_x < 0 or orig_y < 0 or orig_x >= self.camera.width or orig_y >= self.camera.height:
            return
        
        # Обновляем hover состояние кнопок
        self.button_manager.update_hover(orig_x, orig_y)
        
        # Обработка нажатия
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked_button = self.button_manager.handle_click(orig_x, orig_y)
            
            if clicked_button:
                self.logger.info(f"🔘 Button clicked: {clicked_button.text}")
                self._handle_button_action(clicked_button)
    
    def _handle_button_action(self, button):
        """Обработка действий кнопок"""
        if button.text == "VIDEO ONLY":
            pass  # Обрабатывается в button_manager
        
        elif button.text == "MODEL":
            pass  # Обрабатывается в button_manager
        
        elif button.text == "REFINE":
            pass  # Обрабатывается в button_manager
        
        elif button.text == "SAVE":
            # Сохраняем позицию модели
            slider_vals = self.control_window.get_all_values()
            params = self.config_manager.slider_to_params(slider_vals)
            self.config_manager.save_model_position(params)
        
        elif button.text == "LOAD":
            # Загружаем позицию модели
            params = self.config_manager.load_model_position()
            if params:
                slider_vals = self.config_manager.params_to_slider(params)
                self.control_window.set_all_values(slider_vals)
        
        elif button.text == "RESET":
            self.control_window.reset_sliders()
            self.logger.info("🔄 Sliders reset")
        
        elif button.text == "ATTACH":
            if self.marker_detected:
                self.logger.info("🔗 Attaching model to marker...")
                self.auto_center_requested = True
            else:
                self.logger.warning("⚠️ Marker not detected, cannot attach")
        
        elif button.text == "FULL":
            self.display.toggle_fullscreen()
        
        elif button.text == "EXIT":
            self.running = False
    
    def _update_fps(self):
        """Обновление счетчика FPS"""
        self.frame_count += 1
        if self.frame_count % 10 == 0:
            current_time = time.time()
            self.fps = 10 / (current_time - self.last_time)
            self.last_time = current_time
    
    def _process_video_only(self, frame):
        """Обработка в режиме VIDEO ONLY"""
        self.marker_detected = False
        self.pyramid_results_cache = []
        self.n_pyramid_found = 0
        self.refine_reproj_info = (None, None)
        
        # Получаем параметры слайдеров
        slider_vals = self.control_window.get_all_values()
        params = self.config_manager.slider_to_params(slider_vals)
        
        return frame, params, "VIDEO ONLY MODE"
    
        if self.marker_detected:
            # Сохраняем последнюю известную позу
            self.last_known_rvec = target_rvec.copy()
            self.last_known_tvec = target_tvec.copy()
            self.last_apriltag_corners = target_corners.copy()
            
            # Логируем данные об осях (если включено)
            if self.config['debug'].get('log_axes', False):
                self.debug_logger.log_axes_data(
                    frame, target_rvec, target_tvec,
                    self.camera.camera_matrix,
                    self.camera.dist_coeffs,
                    target_corners
                )
            
            # Для отладки можно использовать расширенную отрисовку
            if self.config['debug'].get('debug_text', False):
                frame = draw_axes_debug(
                    frame, target_rvec, target_tvec,
                    self.camera.camera_matrix,
                    self.camera.dist_coeffs
                )
            
            # Автоцентрирование если нужно
            if self.auto_center_requested:
                self._auto_center(target_rvec, target_tvec)
        else:
            # Используем последнюю известную позу
            if self.last_known_rvec is not None:
                target_rvec = self.last_known_rvec
                target_tvec = self.last_known_tvec
                target_corners = self.last_apriltag_corners
                tag_info = "⚠️ USING LAST KNOWN POSITION"
                
                # Рисуем контур по последней известной позиции
                if target_corners is not None:
                    cv2.polylines(frame, [target_corners.astype(np.int32)], 
                                True, (100, 100, 100), 2)
        
        # Уточнение позы
        refine_active = self.button_manager.get_button_state("REFINE")
        
        if refine_active and target_rvec is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame, target_rvec, target_tvec = self._refine_pose(
                gray, frame, target_rvec, target_tvec, target_corners
            )
        
        # Получаем параметры слайдеров
        slider_vals = self.control_window.get_all_values()
        params = self.config_manager.slider_to_params(slider_vals)
        
        # Отрисовка 3D модели
        if self.button_manager.get_button_state("MODEL") and target_rvec is not None:
            self._draw_model(frame, target_rvec, target_tvec, params)
        
        return frame, params, tag_info
    
    def _auto_center(self, rvec, tvec):
        """Автоцентрирование модели"""
        center_3d = np.array([[0, 0, 0]], dtype=np.float32)
        center_2d, _ = cv2.projectPoints(
            center_3d, rvec, tvec,
            self.camera.camera_matrix, self.camera.dist_coeffs
        )
        center_2d = center_2d[0][0]
        dx = self.camera.width // 2 - center_2d[0]
        dy = self.camera.height // 2 - center_2d[1]
        self.logger.info(f"   Offset to center: ({dx:.0f}, {dy:.0f}) px")
        self.auto_center_requested = False
    
    def _refine_pose(self, gray, frame, rvec, tvec, corners):
        """Уточнение позы по пирамиде"""
        # Устанавливаем режим отладки
        self.pyramid_detector.debug = self.config['debug'].get('pyramid', False)
        
        # Детектирование центров граней
        detection_result = self.pyramid_detector.detect(
            gray, rvec, tvec,
            self.camera.camera_matrix,
            self.camera.dist_coeffs
        )
        
        if self.config['debug'].get('pyramid', False) and isinstance(detection_result, tuple):
            self.pyramid_results_cache, debug_frame = detection_result
            cv2.imshow('Pyramid Debug', debug_frame)
        else:
            self.pyramid_results_cache = detection_result
        
        # Подсчет найденных точек
        self.n_pyramid_found = 0
        if isinstance(self.pyramid_results_cache, list):
            for r in self.pyramid_results_cache:
                if isinstance(r, dict) and r.get('center_2d') is not None:
                    self.n_pyramid_found += 1
        
        # Уточнение позы если достаточно точек
        if self.n_pyramid_found >= 2:
            apriltag_obj = self.apriltag_detector.get_object_points()
            rvec, tvec, n_used, reproj_before, reproj_after = self.pose_refiner.refine(
                rvec, tvec,
                apriltag_obj,
                corners,
                self.pyramid_results_cache,
                self.camera.camera_matrix,
                self.camera.dist_coeffs
            )
            self.refine_reproj_info = (reproj_before, reproj_after)
        else:
            self.refine_reproj_info = (None, None)
        
        # Отрисовка результатов
        frame = self.pyramid_detector.draw_results(
            frame, self.pyramid_results_cache,
            rvec, tvec,
            self.camera.camera_matrix,
            self.camera.dist_coeffs
        )
        
        return frame, rvec, tvec
    
    def _draw_model(self, frame, rvec, tvec, params):
        """Отрисовка 3D модели"""
        # Трансформация модели
        T_model_tag = self.model.get_transform_matrix(
            params['scale'],
            params['rot_x'], params['rot_y'], params['rot_z'],
            params['offset_x'], params['offset_y'], params['offset_z']
        )
        
        transformed = self.model.transform(T_model_tag)
        
        if transformed is None:
            return
        
        # Проекция на кадр
        img_points, _ = cv2.projectPoints(
            transformed,
            rvec, tvec,
            self.camera.camera_matrix,
            self.camera.dist_coeffs
        )
        img_points = np.int32(img_points).reshape(-1, 2)
        
        # Отрисовка в зависимости от режима
        mode = params['mode']
        
        if mode == 0:  # Точки
            for pt in img_points:
                if 0 <= pt[0] < self.camera.width and 0 <= pt[1] < self.camera.height:
                    cv2.circle(frame, tuple(pt), 2, (0, 255, 255), -1)
        
        elif mode == 1:  # Ребра
            edges = self.model.get_edges()
            for edge in edges:
                if edge[0] < len(img_points) and edge[1] < len(img_points):
                    pt1 = img_points[edge[0]]
                    pt2 = img_points[edge[1]]
                    if (0 <= pt1[0] < self.camera.width and 0 <= pt1[1] < self.camera.height and
                        0 <= pt2[0] < self.camera.width and 0 <= pt2[1] < self.camera.height):
                        cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 0), 1)
        
        else:  # Полигоны
            for face in self.model.faces:
                if len(face) >= 3:
                    pts = []
                    valid = True
                    for idx in face[:3]:
                        if idx < len(img_points):
                            pt = img_points[idx]
                            if 0 <= pt[0] < self.camera.width and 0 <= pt[1] < self.camera.height:
                                pts.append([pt[0], pt[1]])
                            else:
                                valid = False
                                break
                    if valid and len(pts) == 3:
                        pts = np.array(pts, np.int32)
                        cv2.fillPoly(frame, [pts], (100, 100, 255))

    def _process_normal_mode(self, frame):
        """Обработка в нормальном режиме"""
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Детектирование
        target_rvec, target_tvec, target_corners, tag_info = self.apriltag_detector.detect(
            gray,
            self.camera.camera_matrix,
            self.camera.dist_coeffs
        )
        
        self.marker_detected = target_rvec is not None
        
        if self.marker_detected:
            # Отладочный вывод только если включен verbose
            if self.config['debug'].get('verbose', False):
                print("\n=== CAMERA MATRIX DEBUG ===")
                print(f"Camera matrix:\n{self.camera.camera_matrix}")
                print(f"dist_coeffs: {self.camera.dist_coeffs}")
                print(f"Image size: {self.camera.width}x{self.camera.height}")
                
                # Проверяем проекцию центра маркера
                center_3d = np.array([[0, 0, 0]], dtype=np.float32)
                center_2d, _ = cv2.projectPoints(
                    center_3d, target_rvec, target_tvec,
                    self.camera.camera_matrix, self.camera.dist_coeffs
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
                    self.camera.camera_matrix, self.camera.dist_coeffs
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
            
            self.last_known_rvec = target_rvec.copy()
            self.last_known_tvec = target_tvec.copy()
            self.last_apriltag_corners = target_corners.copy()
            
            # Рисуем контур
            corners = target_corners.astype(np.int32)
            cv2.polylines(frame, [corners], True, (0,255,255), 3)
            
            # Проецируем оси для отрисовки
            axis_points = np.array([
                [0, 0, 0], [0.05, 0, 0], [0, 0.05, 0], [0, 0, 0.05]
            ], dtype=np.float32)
            
            img_points, _ = cv2.projectPoints(
                axis_points, target_rvec, target_tvec,
                self.camera.camera_matrix, self.camera.dist_coeffs
            )
            img_points = img_points.reshape(-1, 2).astype(int)
            
            center = img_points[0]
            x_end = img_points[1]
            y_end = img_points[2]
            z_end = img_points[3]
            
            # Рисуем оси
            cv2.arrowedLine(frame, tuple(center), tuple(x_end), (255, 0, 0), 2, tipLength=0.2)  # X - синий
            cv2.arrowedLine(frame, tuple(center), tuple(y_end), (0, 255, 0), 2, tipLength=0.2)  # Y - зеленый
            cv2.arrowedLine(frame, tuple(center), tuple(z_end), (0, 0, 255), 2, tipLength=0.2)  # Z - красный
            
            # Подписи осей (только если включен debug_text)
            if self.config['debug'].get('debug_text', False):
                cv2.putText(frame, "X", (x_end[0]+5, x_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                cv2.putText(frame, "Y", (y_end[0]+5, y_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(frame, "Z", (z_end[0]+5, z_end[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # Показываем координаты на экране
                cv2.putText(frame, f"Center: ({center[0]}, {center[1]})", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"X: ({x_end[0]}, {x_end[1]})", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                cv2.putText(frame, f"Y: ({y_end[0]}, {y_end[1]})", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.putText(frame, f"Z: ({z_end[0]}, {z_end[1]})", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Рисуем плоскость маркера
            marker_3d = np.array([
                [-0.025, -0.025, 0], [0.025, -0.025, 0],
                [0.025,  0.025, 0], [-0.025,  0.025, 0]
            ], dtype=np.float32)
            
            marker_2d, _ = cv2.projectPoints(
                marker_3d, target_rvec, target_tvec,
                self.camera.camera_matrix, self.camera.dist_coeffs
            )
            marker_2d = marker_2d.reshape(-1, 2).astype(int)
            
            # Рисуем квадрат маркера (только если включен debug_text)
            if self.config['debug'].get('debug_text', False):
                cv2.polylines(frame, [marker_2d], True, (255, 255, 0), 1)
            
            # Рисуем нормаль (всегда, для проверки)
            center_point = tuple(marker_2d.mean(axis=0).astype(int))
            cv2.line(frame, center_point, tuple(z_end), (255, 255, 255), 2)
            if self.config['debug'].get('debug_text', False):
                cv2.putText(frame, "NORMAL", (z_end[0]+5, z_end[1]-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.drawMarker(frame, tuple(z_end), (255, 255, 255), cv2.MARKER_CROSS, 10, 2)
            
            # Логирование в файл (если включено)
            if self.config['debug'].get('log_axes', False):
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
        
        # Уточнение позы
        if self.button_manager.get_button_state("REFINE") and target_rvec is not None:
            frame, target_rvec, target_tvec = self._refine_pose(
                gray, frame, target_rvec, target_tvec, target_corners
            )
        
        # Получаем параметры слайдеров
        slider_vals = self.control_window.get_all_values()
        params = self.config_manager.slider_to_params(slider_vals)
        
        # Отрисовка модели
        if self.button_manager.get_button_state("MODEL") and target_rvec is not None:
            self._draw_model(frame, target_rvec, target_tvec, params)
        
        return frame, params, tag_info

    def run(self):
        """Основной цикл приложения"""
        self.logger.info("🚀 Main loop started")
        
        while self.running:
            # Получение кадра
            frame = self.camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            self._update_fps()
            
            # Выбор режима обработки
            video_only = self.button_manager.get_button_state("VIDEO ONLY")
            
            if video_only:
                frame, params, tag_info = self._process_video_only(frame)
            else:
                frame, params, tag_info = self._process_normal_mode(frame)
            
            # Отрисовка кнопок
            frame = self.button_manager.draw_buttons(frame)
            
            # Создание информационных строк
            info_lines = self.info_overlay.create_info_lines(
                self.fps,
                video_only,
                tag_info,
                params,
                self.marker_detected,
                self.n_pyramid_found,
                self.refine_reproj_info
            )
            
            # Отрисовка информации
            frame = self.info_overlay.draw_info(frame, info_lines)
            
            # Отображение кадра
            display_frame, scale_x, scale_y, x_offset, y_offset = self.display.show_frame(frame)
            
            # Обновление параметров для мыши
            cv2.setMouseCallback(
                self.display.window_name,
                self._mouse_callback,
                {
                    'button_manager': self.button_manager,
                    'scale_x': scale_x,
                    'scale_y': scale_y,
                    'offset_x': x_offset,
                    'offset_y': y_offset
                }
            )
            
            # Обновление окна управления
            if self.config['debug'].get('windows_control_en', True):
                self.control_window.update(
                    self.marker_detected,
                    video_only,
                    self.button_manager.get_button_state("REFINE"),
                    self.n_pyramid_found,
                    self.refine_reproj_info
                )
            
            # Обработка клавиш
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
        
        self.cleanup()
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("👋 Shutting down...")

        # Анализ логов осей
        if self.config['debug'].get('log_axes', False):
            self.debug_logger.analyze_axis_behavior()

        self.camera.release()
        cv2.destroyAllWindows()
        self.logger.info("✅ Done")


def main():
    """Точка входа"""
    tracker = AprilTagTracker()
    tracker.run()


if __name__ == "__main__":
    main()