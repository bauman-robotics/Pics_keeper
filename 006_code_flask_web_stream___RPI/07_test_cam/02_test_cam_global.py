import cv2

# Открываем камеру
cap = cv2.VideoCapture(8)  # /dev/video0

# Даем камере прогреться
cv2.waitKey(1000)

# Захватываем кадр
ret, frame = cap.read()

if ret:
    # Сохраняем снимок
    cv2.imwrite('global_shutter_snapshot.jpg', frame)
    print("✅ Снимок сохранен!")
else:
    print("❌ Не удалось получить кадр")

# Освобождаем камеру
cap.release()