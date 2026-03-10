#!/usr/bin/env python3
"""
Диагностика детектирования AprilTag
"""

import cv2
import numpy as np
from picamera2 import Picamera2
import time

print("🔍 ДИАГНОСТИКА ДЕТЕКТИРОВАНИЯ APRILTAG")
print("="*60)

# 1. Инициализация камеры
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (1536, 864), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()
time.sleep(1)

# 2. Захват кадра
frame_rgb = picam2.capture_array()
frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

# 3. Сохраняем оригинал
cv2.imwrite('diagnostic_original.jpg', frame_bgr)
print("📸 Сохранен: diagnostic_original.jpg")

# 4. Анализ изображения
gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
print(f"\n📊 ХАРАКТЕРИСТИКИ ИЗОБРАЖЕНИЯ:")
print(f"   Размер: {frame_bgr.shape}")
print(f"   Тип: {frame_bgr.dtype}")
print(f"   Яркость (среднее): {np.mean(gray):.1f}")
print(f"   Контраст (std): {np.std(gray):.1f}")
print(f"   Мин/Макс яркость: {np.min(gray)}/{np.max(gray)}")

# 5. Проверка гистограммы
hist = cv2.calcHist([gray], [0], None, [256], [0,256])
print(f"   Распределение:")
print(f"     Темные (0-50): {np.sum(hist[0:50])/np.sum(hist)*100:.1f}%")
print(f"     Средние (51-200): {np.sum(hist[51:200])/np.sum(hist)*100:.1f}%")
print(f"     Светлые (201-255): {np.sum(hist[201:255])/np.sum(hist)*100:.1f}%")

# 6. Тестирование разных словарей
print(f"\n📚 ТЕСТИРОВАНИЕ СЛОВАРЕЙ:")
dictionaries = [
    ('DICT_4X4_50', cv2.aruco.DICT_4X4_50),
    ('DICT_5X5_50', cv2.aruco.DICT_5X5_50),
    ('DICT_6X6_50', cv2.aruco.DICT_6X6_50),
    ('DICT_7X7_50', cv2.aruco.DICT_7X7_50),
    ('DICT_4X4_100', cv2.aruco.DICT_4X4_100),
    ('DICT_5X5_100', cv2.aruco.DICT_5X5_100),
    ('DICT_6X6_100', cv2.aruco.DICT_6X6_100),
    ('DICT_7X7_100', cv2.aruco.DICT_7X7_100),
    ('DICT_4X4_250', cv2.aruco.DICT_4X4_250),
    ('DICT_5X5_250', cv2.aruco.DICT_5X5_250),
    ('DICT_6X6_250', cv2.aruco.DICT_6X6_250),
    ('DICT_7X7_250', cv2.aruco.DICT_7X7_250),
    ('DICT_APRILTAG_16h5', getattr(cv2.aruco, 'DICT_APRILTAG_16h5', None)),
    ('DICT_APRILTAG_25h9', getattr(cv2.aruco, 'DICT_APRILTAG_25h9', None)),
    ('DICT_APRILTAG_36h11', getattr(cv2.aruco, 'DICT_APRILTAG_36h11', None)),
]

for name, dict_id in dictionaries:
    if dict_id is None:
        print(f"   {name:20} ❌ не поддерживается")
        continue
        
    try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        
        corners, ids, rejected = detector.detectMarkers(frame_bgr)
        
        result = f"✅ {len(ids) if ids is not None else 0} маркеров"
        if rejected is not None and len(rejected) > 0:
            result += f", {len(rejected)} отвергнутых"
        
        print(f"   {name:20} {result}")
        
        # Если нашли маркер, сохраняем результат
        if ids is not None and len(ids) > 0:
            debug_frame = frame_bgr.copy()
            cv2.aruco.drawDetectedMarkers(debug_frame, corners, ids)
            cv2.imwrite(f'detected_with_{name}.jpg', debug_frame)
            print(f"      → Сохранен detected_with_{name}.jpg")
            
    except Exception as e:
        print(f"   {name:20} ❌ ошибка: {e}")

# 7. Проверка с разными параметрами для DICT_6X6_250
print(f"\n⚙️ ТЕСТИРОВАНИЕ ПАРАМЕТРОВ (DICT_6X6_250):")

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

param_sets = [
    ("Стандартные", cv2.aruco.DetectorParameters()),
    ("Чувствительные", cv2.aruco.DetectorParameters()),
    ("Очень чувствительные", cv2.aruco.DetectorParameters()),
]

# Настройка параметров
param_sets[1][1].adaptiveThreshConstant = 7
param_sets[1][1].minMarkerPerimeterRate = 0.03
param_sets[1][1].maxMarkerPerimeterRate = 4.0

param_sets[2][1].adaptiveThreshConstant = 10
param_sets[2][1].minMarkerPerimeterRate = 0.02
param_sets[2][1].maxMarkerPerimeterRate = 6.0
param_sets[2][1].minCornerDistanceRate = 0.01
param_sets[2][1].minMarkerDistanceRate = 0.01

for name, params in param_sets:
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, rejected = detector.detectMarkers(frame_bgr)
    
    print(f"   {name:20} → маркеров: {len(ids) if ids is not None else 0}, отвергнуто: {len(rejected) if rejected is not None else 0}")

# 8. Предобработка изображения
print(f"\n🖼️ ТЕСТИРОВАНИЕ ПРЕДОБРАБОТКИ:")

preprocess_methods = [
    ("Оригинал", frame_bgr),
    ("CLAHE", cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY))),
    ("Резкость", cv2.addWeighted(frame_bgr, 1.5, cv2.GaussianBlur(frame_bgr, (0,0), 3), -0.5, 0)),
]

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
params = cv2.aruco.DetectorParameters()
params.adaptiveThreshConstant = 7
detector = cv2.aruco.ArucoDetector(aruco_dict, params)

for name, img in preprocess_methods:
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    corners, ids, rejected = detector.detectMarkers(img)
    print(f"   {name:15} → маркеров: {len(ids) if ids is not None else 0}, отвергнуто: {len(rejected) if rejected is not None else 0}")

picam2.stop()
print("\n✅ Диагностика завершена")