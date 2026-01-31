#!/usr/bin/env python3
"""
Веб-сервер для стриминга видео с веб-камеры (исправленная версия)

не работает. 
"""

from flask import Flask, Response, render_template_string
import cv2
import threading
import time

app = Flask(__name__)

# Глобальные переменные
camera = None
output_frame = None
lock = threading.Lock()
camera_ready = False

# HTML шаблон для отображения видео
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Веб-камера стрим</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            background-color: #f0f0f0;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        img {
            max-width: 90%;
            height: auto;
            border: 3px solid #333;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .info {
            margin-top: 20px;
            color: #666;
        }
        .error {
            color: red;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>🎥 Стрим с веб-камеры</h1>
    <img src="{{ url_for('video_feed') }}" alt="Видео поток">
    <div class="info">
        <p>Видео транслируется в реальном времени</p>
        <p class="error" id="error-msg" style="display:none;">Ожидание видео...</p>
    </div>
    <script>
        // Проверка загрузки изображения
        const img = document.querySelector('img');
        const errorMsg = document.getElementById('error-msg');
        
        img.onerror = function() {
            errorMsg.style.display = 'block';
        };
        
        img.onload = function() {
            errorMsg.style.display = 'none';
        };
    </script>
</body>
</html>
"""

def init_camera():
    """Инициализация камеры"""
    global camera
    
    # Попробуем разные индексы камеры
    for camera_index in [0, 1, 2]:
        print(f"Попытка открыть камеру с индексом {camera_index}...")
        camera = cv2.VideoCapture(camera_index)
        
        if camera.isOpened():
            print(f"✅ Камера {camera_index} успешно открыта!")
            break
        else:
            camera.release()
    
    if not camera.isOpened():
        raise RuntimeError("❌ Не удалось открыть веб-камеру")
    
    # Настройка разрешения
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    
    # Проверяем, что камера действительно работает
    ret, test_frame = camera.read()
    if not ret or test_frame is None:
        raise RuntimeError("❌ Камера открыта, но не может захватить кадр")
    
    print(f"📐 Разрешение: {int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"🎞️  FPS: {int(camera.get(cv2.CAP_PROP_FPS))}")
    
    return camera

def get_frame():
    """Захват кадра с камеры"""
    global output_frame, lock, camera, camera_ready
    
    frame_count = 0
    error_count = 0
    
    print("🎬 Поток захвата кадров запущен...")
    
    while True:
        try:
            success, frame = camera.read()
            
            if not success or frame is None:
                error_count += 1
                print(f"⚠️  Ошибка захвата кадра #{error_count}")
                time.sleep(0.1)
                if error_count > 10:
                    print("❌ Слишком много ошибок, проверьте камеру")
                    break
                continue
            
            error_count = 0  # Сброс счетчика ошибок
            frame_count += 1
            
            # Добавляем информацию на кадр
            cv2.putText(frame, f"Frame: {frame_count}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"), (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            with lock:
                output_frame = frame.copy()
                if not camera_ready:
                    camera_ready = True
                    print(f"✅ Первый кадр захвачен! (кадр #{frame_count})")
            
            # Небольшая задержка для снижения нагрузки
            time.sleep(0.03)  # ~30 FPS
            
            if frame_count % 100 == 0:
                print(f"📊 Захвачено кадров: {frame_count}")
                
        except Exception as e:
            print(f"❌ Ошибка в потоке захвата: {e}")
            time.sleep(0.5)

def generate_frames():
    """Генератор кадров для стриминга"""
    global output_frame, lock, camera_ready
    
    print("📡 Клиент подключился к видео потоку")
    
    # Ждем, пока камера будет готова
    wait_count = 0
    while not camera_ready and wait_count < 50:
        time.sleep(0.1)
        wait_count += 1
    
    if not camera_ready:
        print("⚠️  Камера не готова после ожидания")
    
    frame_sent = 0
    
    while True:
        with lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            
            # Кодирование кадра в JPEG
            (flag, encoded_image) = cv2.imencode(".jpg", output_frame, 
                                                  [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if not flag:
                continue
        
        frame_sent += 1
        
        # Отправка кадра в формате multipart
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + 
               bytearray(encoded_image) + b'\r\n')

@app.route('/')
def index():
    """Главная страница"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/video_feed')
def video_feed():
    """Эндпоинт для видео потока"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Проверка статуса камеры"""
    return {
        'camera_ready': camera_ready,
        'camera_opened': camera.isOpened() if camera else False,
        'frame_available': output_frame is not None
    }

if __name__ == '__main__':
    try:
        # Инициализация камеры
        print("🔧 Инициализация веб-камеры...")
        init_camera()
        
        # Запуск потока захвата видео
        print("🚀 Запуск потока захвата кадров...")
        thread = threading.Thread(target=get_frame, daemon=True)
        thread.start()
        
        # Даем время на захват первого кадра
        print("⏳ Ожидание первого кадра...")
        time.sleep(2)
        
        print("\n" + "="*50)
        print("🚀 Сервер запущен!")
        print("📹 Откройте в браузере: http://localhost:5000")
        print(f"   Или с другого устройства: http://10.8.1.2:5000")
        print("🔍 Статус камеры: http://localhost:5000/status")
        print("⏹️  Для остановки нажмите Ctrl+C")
        print("="*50 + "\n")
        
        # Запуск Flask сервера
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка сервера...")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
        print("✅ Камера освобождена. До свидания!")