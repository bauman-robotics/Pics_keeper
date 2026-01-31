#!/usr/bin/env python3
"""
Скрипт для потоковой передачи с веб-камеры через HTTP-сервер
Использует OpenCV для захвата видео и создает MJPEG стрим
"""

import cv2
import threading
import time
import argparse
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import numpy as np
import os
import signal
import sys

class StreamingHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов для потоковой передачи MJPEG"""
    
    def do_GET(self):

        print(f"📥 Запрос: {self.path}")  # Добавьте эту строку для отладки
        
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8') 
            self.end_headers()          
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Webcam Stream</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        background-color: #f0f0f0;
                        margin: 0;
                        padding: 20px;
                    }}
                    h1 {{
                        color: #333;
                    }}
                    #video-container {{
                        margin: 20px auto;
                        max-width: 90%;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                        border: 3px solid #333;
                        border-radius: 10px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .controls {{
                        margin: 20px;
                    }}
                    button {{
                        padding: 10px 20px;
                        margin: 5px;
                        font-size: 16px;
                        cursor: pointer;
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 5px;
                    }}
                    button:hover {{
                        background-color: #45a049;
                    }}
                    .info {{
                        margin-top: 20px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <h1>🎥 Webcam Stream</h1>
                <div class="controls">
                    <button onclick="startStream()">Старт стрима</button>
                    <button onclick="takeSnapshot()">Снимок</button>
                </div>
                <div id="video-container">
                    <img id="stream" src="" alt="Видео поток" style="display:none;">
                </div>
                <div class="info">
                    <p id="status">Нажмите "Старт стрима" для начала</p>
                </div>
                <script>
                    function startStream() {{
                        const img = document.getElementById('stream');
                        img.src = '/video_feed';
                        img.style.display = 'block';
                        document.getElementById('status').textContent = 'Стрим активен';
                    }}
                    
                    function takeSnapshot() {{
                        const img = document.getElementById('stream');
                        const canvas = document.createElement('canvas');
                        canvas.width = img.naturalWidth;
                        canvas.height = img.naturalHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        
                        const link = document.createElement('a');
                        link.download = 'snapshot_' + Date.now() + '.jpg';
                        link.href = canvas.toDataURL('image/jpeg');
                        link.click();
                    }}
                </script>
            </body>
            </html>
            """.format()  # Удалите параметры из format() если они есть
            
            self.wfile.write(html.encode())

        elif self.path == '/video_feed':
                print("🎬 Запущен video_feed")  # Отладка
                self.send_response(200)
                self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                
                try:
                    while True:
                        frame = camera.get_frame()
                        if frame is None:
                            print("⚠️ Нет кадра")
                            break
                        
                        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(jpeg)))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                except Exception as e:
                    print(f"❌ Ошибка в video_feed: {e}")
            
        else:
            self.send_response(404)
            self.end_headers()            

    def log_message(self, format, *args):
        # Отключаем стандартное логирование
        pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Многопоточный HTTP сервер"""
    allow_reuse_address = True
    daemon_threads = True
    
    def __init__(self, server_address, RequestHandlerClass, camera_id, capture_width, 
                 capture_height, fps, quality):
        super().__init__(server_address, RequestHandlerClass)
        self.camera_id = camera_id
        self.capture_width = capture_width
        self.capture_height = capture_height
        self.fps = fps
        self.quality = quality
        self.streaming_active = True
        self.frame = None
        self.clients = []
        self.start_time = time.time()

class CameraThread(threading.Thread):
    """Поток для захвата видео с камеры"""
    def __init__(self, camera_id, width, height, fps):
        super().__init__()
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.running = True
        self.cap = None
        
    def run(self):
        """Захват видео с камеры"""
        print(f"Запуск захвата с камеры {self.camera_id}...")
        
        # Пробуем разные методы открытия камеры
        camera_sources = [
            self.camera_id,  # Как число
            f'/dev/video{self.camera_id}',  # Как путь
            int(self.camera_id)  # Как integer
        ]
        
        for source in camera_sources:
            try:
                self.cap = cv2.VideoCapture(source)
                if self.cap.isOpened():
                    print(f"Камера открыта через источник: {source}")
                    break
            except:
                continue
        
        if not self.cap or not self.cap.isOpened():
            print("Не удалось открыть камеру. Пробую доступные камеры...")
            
            # Пробуем найти рабочую камеру
            for i in range(0, 5):
                self.cap = cv2.VideoCapture(i)
                if self.cap.isOpened():
                    print(f"Найдена камера #{i}")
                    self.camera_id = i
                    break
            
            if not self.cap or not self.cap.isOpened():
                print("Ошибка: не найдено ни одной доступной камеры!")
                return
        
        # Настройка параметров камеры
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Получаем реальные параметры
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"Реальные параметры камеры:")
        print(f"  Разрешение: {actual_width}x{actual_height}")
        print(f"  FPS: {actual_fps}")
        
        # Основной цикл захвата кадров
        while self.running and server.streaming_active:
            ret, frame = self.cap.read()
            
            if ret:
                # Сохраняем кадр для сервера
                server.frame = frame
            else:
                print("Ошибка захвата кадра")
                time.sleep(0.1)
            
            # Поддержка FPS
            time.sleep(1.0 / self.fps)
        
        # Освобождение ресурсов
        if self.cap:
            self.cap.release()
        print("Захват видео остановлен")
    
    def stop(self):
        """Остановка потока захвата"""
        self.running = False

def get_local_ip():
    """Получение локального IP адреса"""
    try:
        # Создаем временное соединение, чтобы определить IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def signal_handler(sig, frame):
    """Обработчик сигналов для graceful shutdown"""
    print("\n🛑 Получен сигнал остановки...")
    server.streaming_active = False
    time.sleep(1)
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description='HTTP сервер для потоковой передачи с веб-камеры'
    )
    
    parser.add_argument('--port', type=int, default=8080,
                       help='Порт HTTP сервера (по умолчанию: 8080)')
    
    parser.add_argument('--camera', type=int, default=0,
                       help='ID камеры (0, 1, 2, ...) (по умолчанию: 0)')
    
    parser.add_argument('--width', type=int, default=640,
                       help='Ширина кадра (по умолчанию: 640)')
    
    parser.add_argument('--height', type=int, default=480,
                       help='Высота кадра (по умолчанию: 480)')
    
    parser.add_argument('--fps', type=int, default=30,
                       help='FPS потока (по умолчанию: 30)')
    
    parser.add_argument('--quality', type=int, default=85,
                       help='Качество JPEG (1-100) (по умолчанию: 85)')
    
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Хост для сервера (по умолчанию: 0.0.0.0)')
    
    args = parser.parse_args()
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    global server
    local_ip = get_local_ip()
    
    print(f"""
    🎥 Webcam Stream Server
    {'='*50}
    📷 Камера: #{args.camera}
    📐 Разрешение: {args.width}x{args.height}
    🎬 FPS: {args.fps}
    📊 Качество: {args.quality}%
    🌐 Хост: {args.host}
    🔌 Порт: {args.port}
    {'='*50}
    """)
    
    try:
        # Создаем HTTP сервер
        server = ThreadedHTTPServer(
            (args.host, args.port),
            StreamingHandler,
            args.camera,
            args.width,
            args.height,
            args.fps,
            args.quality
        )
        
        # Запускаем поток захвата видео
        camera_thread = CameraThread(args.camera, args.width, args.height, args.fps)
        camera_thread.daemon = True
        camera_thread.start()
        
        # Даем время камере инициализироваться
        time.sleep(2)
        
        print(f"""
    🚀 Сервер запущен!
    {'='*50}
    🌐 Локальный доступ: http://localhost:{args.port}
    🔗 Сетевой доступ: http://{local_ip}:{args.port}
    {'='*50}
    📝 Инструкции:
      1. Откройте браузер по указанному URL
      2. Нажмите "Старт стрима" для начала просмотра
      3. Используйте "Снимок" для сохранения кадра
      4. Нажмите Ctrl+C для остановки сервера
    {'='*50}
        """)
        
        # Запускаем сервер
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Остановка сервера по запросу пользователя...")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        # Останавливаем все потоки
        if 'server' in globals():
            server.streaming_active = False
        
        if 'camera_thread' in locals():
            camera_thread.stop()
            camera_thread.join(timeout=2)
        
        print("✅ Сервер остановлен. До свидания!")

if __name__ == "__main__":
    main()