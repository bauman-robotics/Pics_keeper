import cv2
import numpy as np
import glob
import os

# ===== НАСТРОЙКИ =====
# Укажите путь к папке со снимками (ваш путь)
# IMAGES_PATH = '/home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI/static/photos/*.jpg'
# IMAGES_PATH = '/home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI/imx708_calibr_photos/*.jpg'

IMAGES_PATH = '/home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI/photos_calibr_g_shutter_IR/*.jpg'

# Размер шахматной доски (количество внутренних углов)
# Обычно это (ширина-1) x (высота-1) в клетках
CHESSBOARD_SIZE = (7, 7)  # 7 углов по ширине, 7 по высоте

# Размер клетки в МИЛЛИМЕТРАХ (измерьте вашу распечатку!)
SQUARE_SIZE_MM = 50  # если ваша клетка 50 мм

# ===== ПАРАМЕТРЫ РАЗРЕШЕНИЯ =====
# Укажите разрешение, в котором проводилась съемка
# Это важно для правильного масштабирования параметров
CALIBRATION_WIDTH = 1920   # ширина снимков для калибровки
CALIBRATION_HEIGHT = 1200  # высота снимков для калибровки

# Целевое разрешение, для которого будут масштабированы параметры
# Оставьте None, если масштабирование не нужно
TARGET_WIDTH = 1920        # желаемая ширина (или None)
TARGET_HEIGHT = 1200        # желаемая высота (или None)

# ===== ПОДГОТОВКА =====
# Критерии остановки итеративного уточнения углов
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# Подготовка 3D точек объекта
objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 
                        0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2) * SQUARE_SIZE_MM

# Массивы для хранения точек
objpoints = []  # 3D точки в реальном мире
imgpoints = []  # 2D точки на изображении

# ===== ЗАГРУЗКА ИЗОБРАЖЕНИЙ =====
images = glob.glob(IMAGES_PATH)
print(f"Найдено изображений: {len(images)}")
print(f"Разрешение калибровки: {CALIBRATION_WIDTH}x{CALIBRATION_HEIGHT}")

if TARGET_WIDTH and TARGET_HEIGHT:
    print(f"Целевое разрешение: {TARGET_WIDTH}x{TARGET_HEIGHT}")
    scale_x = TARGET_WIDTH / CALIBRATION_WIDTH
    scale_y = TARGET_HEIGHT / CALIBRATION_HEIGHT
    print(f"Коэффициенты масштабирования: x={scale_x:.2f}, y={scale_y:.2f}")

if len(images) < 5:
    print("ОШИБКА: Нужно минимум 5 изображений для калибровки!")
    exit()

# Создаем папку для результатов
os.makedirs('calibration_results', exist_ok=True)

good_images = 0
bad_images = []

# ===== ПОИСК УГЛОВ НА ВСЕХ ИЗОБРАЖЕНИЯХ =====
for i, fname in enumerate(images):
    print(f"\nОбработка {i+1}/{len(images)}: {os.path.basename(fname)}")
    
    img = cv2.imread(fname)
    
    # Проверяем соответствие разрешения
    h, w = img.shape[:2]
    if w != CALIBRATION_WIDTH or h != CALIBRATION_HEIGHT:
        print(f"  ⚠️  Предупреждение: изображение имеет размер {w}x{h}, "
              f"ожидалось {CALIBRATION_WIDTH}x{CALIBRATION_HEIGHT}")
        print(f"     Изображение будет изменено до нужного размера")
        img = cv2.resize(img, (CALIBRATION_WIDTH, CALIBRATION_HEIGHT))
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Поиск углов шахматной доски
    ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)
    
    if ret:
        objpoints.append(objp)
        
        # Уточнение углов до субпиксельной точности
        corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
        imgpoints.append(corners2)
        good_images += 1
        
        # Визуализация для проверки
        cv2.drawChessboardCorners(img, CHESSBOARD_SIZE, corners2, ret)
        
        # Сохраняем изображение с отмеченными углами
        output_path = f'calibration_results/checked_{os.path.basename(fname)}'
        cv2.imwrite(output_path, img)
        print(f"  ✅ Углы найдены! Результат сохранен в {output_path}")
        
        # Показываем на экране (нажмите любую клавишу для продолжения)
        cv2.imshow('Check_angles', img)
        cv2.waitKey(500)  # показываем 0.5 секунды
    else:
        bad_images.append(os.path.basename(fname))
        print(f"  ❌ Углы НЕ найдены")

cv2.destroyAllWindows()

# ===== ИТОГИ ПОИСКА УГЛОВ =====
print("\n" + "="*50)
print(f"ИТОГИ: Успешно обработано: {good_images} из {len(images)}")
if bad_images:
    print(f"Не удалось найти углы на:")
    for fname in bad_images:
        print(f"  - {fname}")

if good_images < 5:
    print("\n❌ ОШИБКА: Слишком мало изображений с распознанными углами!")
    print("   Сделайте еще снимков, следя чтобы вся доска была в кадре.")
    exit()

# ===== КАЛИБРОВКА =====
print("\n🔄 Выполняется калибровка...")
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
    objpoints, imgpoints, gray.shape[::-1], None, None)

# ===== МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ (если нужно) =====
if TARGET_WIDTH and TARGET_HEIGHT:
    mtx_scaled = mtx.copy()
    mtx_scaled[0,0] *= scale_x  # fx
    mtx_scaled[1,1] *= scale_y  # fy
    mtx_scaled[0,2] *= scale_x  # cx
    mtx_scaled[1,2] *= scale_y  # cy
else:
    mtx_scaled = None
    scale_x = scale_y = 1.0

# ===== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =====
np.save('calibration_results/camera_matrix.npy', mtx)
np.save('calibration_results/dist_coeffs.npy', dist)

if mtx_scaled is not None:
    np.save('calibration_results/camera_matrix_scaled.npy', mtx_scaled)

# Сохраняем в текстовом формате для удобства
with open('calibration_results/calibration_params.txt', 'w') as f:
    f.write(f"ПАРАМЕТРЫ КАЛИБРОВКИ\n")
    f.write(f"{'='*50}\n\n")
    f.write(f"Разрешение калибровки: {CALIBRATION_WIDTH}x{CALIBRATION_HEIGHT}\n")
    if TARGET_WIDTH and TARGET_HEIGHT:
        f.write(f"Целевое разрешение: {TARGET_WIDTH}x{TARGET_HEIGHT}\n")
        f.write(f"Коэффициенты масштабирования: x={scale_x:.2f}, y={scale_y:.2f}\n")
    f.write(f"\nОшибка репроекции: {ret:.6f}\n\n")
    
    f.write("МАТРИЦА КАМЕРЫ (для разрешения калибровки):\n")
    f.write(str(mtx) + "\n\n")
    f.write(f"fx = {mtx[0,0]:.2f}, fy = {mtx[1,1]:.2f}\n")
    f.write(f"cx = {mtx[0,2]:.2f}, cy = {mtx[1,2]:.2f}\n\n")
    
    if mtx_scaled is not None:
        f.write(f"МАТРИЦА КАМЕРЫ (масштабированная для {TARGET_WIDTH}x{TARGET_HEIGHT}):\n")
        f.write(str(mtx_scaled) + "\n\n")
        f.write(f"fx = {mtx_scaled[0,0]:.2f}, fy = {mtx_scaled[1,1]:.2f}\n")
        f.write(f"cx = {mtx_scaled[0,2]:.2f}, cy = {mtx_scaled[1,2]:.2f}\n\n")
    
    f.write("КОЭФФИЦИЕНТЫ ДИСТОРСИИ (не зависят от разрешения):\n")
    f.write(str(dist.reshape(-1)) + "\n")
    f.write("Формат: [k1, k2, p1, p2, k3]\n")

# ===== ВЫВОД РЕЗУЛЬТАТОВ =====
print("\n" + "="*50)
print("РЕЗУЛЬТАТЫ КАЛИБРОВКИ:")
print("="*50)
print(f"\n📊 Ошибка репроекции: {ret:.6f}")
print("   (чем меньше, тем лучше; <0.5 - отлично, 0.5-1.0 - хорошо)")

print(f"\n📷 Разрешение калибровки: {CALIBRATION_WIDTH}x{CALIBRATION_HEIGHT}")
print("\n📷 Матрица камеры (для разрешения калибровки):")
print(mtx)
print("\n   Параметры (для вашего кода):")
print(f"   fx = {mtx[0,0]:.2f}, fy = {mtx[1,1]:.2f}")
print(f"   cx = {mtx[0,2]:.2f}, cy = {mtx[1,2]:.2f}")

if mtx_scaled is not None:
    print(f"\n📷 Матрица камеры (масштабированная для {TARGET_WIDTH}x{TARGET_HEIGHT}):")
    print(mtx_scaled)
    print("\n   Параметры (для вашего кода):")
    print(f"   fx = {mtx_scaled[0,0]:.2f}, fy = {mtx_scaled[1,1]:.2f}")
    print(f"   cx = {mtx_scaled[0,2]:.2f}, cy = {mtx_scaled[1,2]:.2f}")

print("\n🔧 Коэффициенты дисторсии (dist_coeffs):")
print(dist.reshape(-1))
print("\n   Формат: [k1, k2, p1, p2, k3]")
print("   (не зависят от разрешения)")

# ===== ВИЗУАЛЬНАЯ ПРОВЕРКА =====
print("\n🔄 Выполняется визуальная проверка на первом снимке...")

# Берем первое изображение для проверки
test_img = cv2.imread(images[0])
h, w = test_img.shape[:2]

# Исправляем дисторсию
newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))
dst = cv2.undistort(test_img, mtx, dist, None, newcameramtx)

# Обрезаем изображение по ROI (область без черных краев)
x, y, w_roi, h_roi = roi
dst_cropped = dst[y:y+h_roi, x:x+w_roi]

# Сохраняем результаты проверки
cv2.imwrite('calibration_results/original_test.jpg', test_img)
cv2.imwrite('calibration_results/undistorted_test.jpg', dst)
cv2.imwrite('calibration_results/undistorted_cropped.jpg', dst_cropped)

# Показываем на экране
cv2.imshow('Original', cv2.resize(test_img, (640, 480)))
cv2.imshow('After_calibr', cv2.resize(dst, (640, 480)))
cv2.imshow('After_calibr_(cut)', cv2.resize(dst_cropped, (640, 480)))

print("\n✅ Результаты сохранены в папке 'calibration_results':")
print("   - camera_matrix.npy (для загрузки в Python)")
print("   - dist_coeffs.npy")
if mtx_scaled is not None:
    print("   - camera_matrix_scaled.npy (масштабированная матрица)")
print("   - calibration_params.txt (читаемый формат)")
print("   - original_test.jpg (оригинал)")
print("   - undistorted_test.jpg (исправленное)")
print("   - undistorted_cropped.jpg (обрезанное)")

print("\n📌 На экране показаны результаты. Нажмите любую клавишу для выхода...")
cv2.waitKey(0)
cv2.destroyAllWindows()