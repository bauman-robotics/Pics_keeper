#!/usr/bin/env python3
"""
Flask Web Server for Webcam Streaming - Version 2
HTML templates moved to separate templates directory
"""

from flask import Flask, Response, render_template, jsonify
import cv2
import sys
import threading
import time

app = Flask(__name__, template_folder='templates_03')

# Глобальные переменные для управления стримом
stream_active = False
stream_thread = None
frame_count = 0
camera = None

def test_camera_backends():
    """Тестируем разные способы открытия камеры"""
    
    backends = [
        ("Default", 0, None),
        ("V4L2 video0", 0, cv2.CAP_V4L2),
        ("V4L2 video1", 1, cv2.CAP_V4L2),
        ("FFMPEG video0", 0, cv2.CAP_FFMPEG),
        ("Direct /dev/video0", "/dev/video0", cv2.CAP_V4L2),
        ("Direct /dev/video1", "/dev/video1", cv2.CAP_V4L2),
    ]
    
    for name, device, backend in backends:
        print(f"\nПробую {name}...")
        try:
            if backend is None:
                cam = cv2.VideoCapture(device)
            else:
                cam = cv2.VideoCapture(device, backend)
            
            if cam.isOpened():
                ret, frame = cam.read()
                if ret and frame is not None:
                    print(f"✅ {name} РАБОТАЕТ!")
                    print(f"   Разрешение: {frame.shape[1]}x{frame.shape[0]}")
                    return cam
                else:
                    print(f"⚠️  {name} открылась, но не может читать кадры")
                    cam.release()
            else:
                print(f"❌ {name} не открылась")
                cam.release()
        except Exception as e:
            print(f"❌ {name} ошибка: {e}")
    
    return None

print("=" * 60)
print("🔍 Поиск рабочей камеры...")
print("=" * 60)

camera = test_camera_backends()

if camera is None:
    print("\n❌ НЕ НАЙДЕНА РАБОЧАЯ КАМЕРА!")
    print("\nПопробуйте:")
    print("  1. sudo apt install v4l-utils")
    print("  2. v4l2-ctl -d /dev/video0 --list-formats-ext")
    print("  3. cheese  (для теста камеры)")
    sys.exit(1)

print("\n✅ Камера найдена и готова к работе!")
print("=" * 60)

def generate():
    """Генератор кадров для потоковой передачи"""
    global stream_active, frame_count
    print("🎬 Генератор кадров запущен")
    local_frame_count = 0
    error_count = 0
    
    while stream_active:
        success, frame = camera.read()
        
        if not success or frame is None:
            error_count += 1
            print(f"❌ Ошибка чтения кадра #{local_frame_count}, попытка {error_count}")
            
            if error_count > 10:
                print("💥 Слишком много ошибок, останавливаем стрим")
                break
            continue
        
        error_count = 0  # Сброс счетчика ошибок
        local_frame_count += 1
        frame_count += 1
        
        if local_frame_count % 30 == 0:
            print(f"📊 Отправлено кадров: {local_frame_count}")
        
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            print("⚠️ Ошибка кодирования JPEG")
            continue
        
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    print("🎬 Генератор кадров остановлен")

@app.route('/')
def index():
    """Главная страница с видео потоком"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Маршрут для видео потока"""
    print("📹 Клиент запросил video_feed")
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """Страница статуса сервера"""
    return render_template('status.html')

@app.route('/api/stream/start', methods=['POST'])
def start_stream():
    """Запуск видеопотока"""
    global stream_active
    if not stream_active:
        stream_active = True
        print("🎬 Стрим запущен")
        return jsonify({'status': 'started', 'message': 'Видеопоток запущен'})
    else:
        return jsonify({'status': 'already_running', 'message': 'Видеопоток уже запущен'})

@app.route('/api/stream/stop', methods=['POST'])
def stop_stream():
    """Остановка видеопотока"""
    global stream_active
    if stream_active:
        stream_active = False
        print("🎬 Стрим остановлен")
        return jsonify({'status': 'stopped', 'message': 'Видеопоток остановлен'})
    else:
        return jsonify({'status': 'already_stopped', 'message': 'Видеопоток уже остановлен'})

@app.route('/api/stream/status')
def stream_status():
    """Получение статуса видеопотока"""
    global stream_active, frame_count
    return jsonify({
        'stream_active': stream_active,
        'frame_count': frame_count,
        'camera_connected': camera is not None and camera.isOpened()
    })

if __name__ == '__main__':
    try:
        print("\n🚀 Запуск сервера на http://localhost:5000")
        print("=" * 60)
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка...")
    finally:
        if camera:
            camera.release()
        print("✅ Камера освобождена")