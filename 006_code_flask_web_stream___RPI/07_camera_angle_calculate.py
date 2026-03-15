import cv2
import numpy as np

# Загрузите матрицу камеры
camera_matrix = np.load('calibration_results_g_shutter_IR/camera_matrix.npy')

# Параметры
image_size = (1920, 1200)  # ваше разрешение
aperture_width = 0  # если неизвестно - 0
aperture_height = 0  # если неизвестно - 0

# Получить углы обзора
fov_x, fov_y, focal_length_2d, principal_point, aspect_ratio = \
    cv2.calibrationMatrixValues(camera_matrix, image_size, aperture_width, aperture_height)

print(f"Угол обзора по горизонтали: {fov_x:.2f} градусов")
print(f"Угол обзора по вертикали: {fov_y:.2f} градусов")
