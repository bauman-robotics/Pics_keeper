#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Рабочий веб-сервер для стриминга
"""

from flask import Flask, Response, render_template
import cv2
import threading
import time
import sys

app = Flask(__name__)

class VideoCamera:
    def __init__(self, src=0):
        print(f"🔧 Инициализация камеры {src}...")
        
        self.camera = cv2.VideoCapture(src)
        if not self.camera.isOpened():
            raise RuntimeError(f"❌ Не удалось открыть камеру")
        
        # Простые настройки
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()
        
        # Запускаем поток
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        
        # Ждем первый кадр
        time.sleep(0.5)
        print(f"✅ Камера готова")
    
    def _update(self):
        while not self.stopped:
            ret, frame = self.camera.read()
            if ret:
                with self.lock:
                    self.frame = frame
            time.sleep(0.01)
    
    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
    
    def stop(self):
        self.stopped = True
        self.camera.release()

camera = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def generate():
        print("📡 Клиент подключился")
        frame_num = 0
        
        while True:
            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            
            # Кодируем кадр
            success, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not success:
                continue
            
            frame_num += 1
            if frame_num % 50 == 0:
                print(f"📊 Кадр #{frame_num}")
            
            # КРИТИЧНО: правильный формат multipart
            frame_data = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n'
                   b'\r\n' + frame_data + b'\r\n')
    
    response = Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Accel-Buffering'] = 'no'
    
    return response

if __name__ == '__main__':
    try:
        print("=" * 60)
        camera = VideoCamera(0)
        print("=" * 60)
        print("🚀 Сервер: http://localhost:5000")
        print("=" * 60)
        
        # ВАЖНО: threaded=True для множественных соединений
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    
    except KeyboardInterrupt:
        print("\n⏹️ Остановка...")
    finally:
        if camera:
            camera.stop()
        print("✅ Готово")