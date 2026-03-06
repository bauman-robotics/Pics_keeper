import cv2
import numpy as np
import glob
import os

# ===== НАСТРОЙКИ =====
# Укажите путь к папке со снимками (ваш путь)
#IMAGES_PATH = '/home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI/static/photos/*.jpg'
IMAGES_PATH = '/home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI/imx708_calibr_photos/*.jpg'

# Размер шахматной доски (количество внутренних углов)
# Обычно это (ширина-1) x (высота-1) в клетках
CHESSBOARD_SIZE = (7, 7)  # 7 углов по ширине, 7 по высоте

# Размер клетки в МИЛЛИМЕТРАХ (измерьте вашу распечатку!)
SQUARE_SIZE_MM = 50  # если ваша клетка 50 мм

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

# ===== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =====
np.save('calibration_results/camera_matrix.npy', mtx)
np.save('calibration_results/dist_coeffs.npy', dist)

# Сохраняем в текстовом формате для удобства
with open('calibration_results/calibration_params.txt', 'w') as f:
    f.write(f"Ошибка репроекции (reprojection error): {ret}\n\n")
    f.write("Матрица камеры (camera_matrix):\n")
    f.write(str(mtx) + "\n\n")
    f.write("Коэффициенты дисторсии (dist_coeffs):\n")
    f.write(str(dist) + "\n\n")

# ===== ВЫВОД РЕЗУЛЬТАТОВ =====
print("\n" + "="*50)
print("РЕЗУЛЬТАТЫ КАЛИБРОВКИ:")
print("="*50)
print(f"\n📊 Ошибка репроекции: {ret:.6f}")
print("   (чем меньше, тем лучше; <0.5 - отлично, 0.5-1.0 - хорошо)")

print("\n📷 Матрица камеры (camera_matrix):")
print(mtx)
print("\n   Параметры (для вашего кода):")
print(f"   fx = {mtx[0,0]:.2f}, fy = {mtx[1,1]:.2f}")
print(f"   cx = {mtx[0,2]:.2f}, cy = {mtx[1,2]:.2f}")

print("\n🔧 Коэффициенты дисторсии (dist_coeffs):")
print(dist.reshape(-1))
print("\n   Формат: [k1, k2, p1, p2, k3]")

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
print("   - calibration_params.txt (читаемый формат)")
print("   - original_test.jpg (оригинал)")
print("   - undistorted_test.jpg (исправленное)")
print("   - undistorted_cropped.jpg (обрезанное)")

print("\n📌 На экране показаны результаты. Нажмите любую клавишу для выхода...")
cv2.waitKey(0)
cv2.destroyAllWindows()