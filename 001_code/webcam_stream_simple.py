#!/usr/bin/env python3
"""
Простой MJPEG стрим для веб-камеры

Повторяет функциональность из 01_pics_keeper.py, но для веб-камеры.
"""

import cv2
import time
import threading
import socket
import json
import math
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from utils.webcam_capture import WebcamCapture
from utils.logger import create_logger
import numpy as np

class WebcamStreamHandler(SimpleHTTPRequestHandler):
    """Обработчик HTTP запросов для веб-камеры"""
    
    def log_message(self, format, *args):
        pass  # Отключаем стандартные логи
    
    def do_GET(self):
        """Обработка GET запросов"""
        
        if self.path == '/stream.mjpg':
            # MJPEG стрим
            self.send_stream()
            
        elif self.path == '/':
            # Главная страница
            self.send_main_page()
            
        elif self.path == '/capture':
            # Захват кадра
            self.capture_frame()
            
        elif self.path == '/status':
            # Статус
            self.send_status()
            
        elif self.path == '/snapshot':
            # Быстрый снимок
            self.send_snapshot()
            
        else:
            super().do_GET()
    
    def send_stream(self):
        """Отправка MJPEG стрима"""
        print(f"🔄 Подключение к стриму от {self.client_address[0]}")
        
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        
        try:
            frame_count = 0
            last_stats_time = time.time()
            
            while True:
                # Получаем кадр
                frame = self.server.get_latest_frame()
                
                if frame is not None and frame.size > 0:
                    # Кодируем в JPEG
                    ret, jpeg = cv2.imencode('.jpg', frame, 
                                            [cv2.IMWRITE_JPEG_QUALITY, self.server.stream_quality])
                    
                    if ret:
                        # Отправляем кадр
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(jpeg))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        
                        frame_count += 1
                        
                        # Статистика каждые 5 секунд
                        if time.time() - last_stats_time >= 5:
                            fps = frame_count / 5
                            print(f"📊 Стрим: {fps:.1f} FPS")
                            frame_count = 0
                            last_stats_time = time.time()
                else:
                    time.sleep(0.01)
                        
        except Exception as e:
            print(f"🔌 Отключение от стрима: {e}")
    
    def send_main_page(self):
        """Главная страница"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        
        hostname = socket.gethostname()
        camera_name = self.server.camera_name
        stream_res = f"{self.server.stream_width}x{self.server.stream_height}"
        port = self.server.server_port
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Веб-камера: {camera_name}</title>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background: #1a1a1a;
                    color: #fff;
                    font-family: Arial, sans-serif;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                h1 {{
                    text-align: center;
                    color: #4CAF50;
                }}
                .info {{
                    background: #2a2a2a;
                    padding: 15px;
                    border-radius: 10px;
                    margin: 20px 0;
                }}
                .stream-container {{
                    text-align: center;
                    background: #000;
                    padding: 10px;
                    border-radius: 10px;
                    margin: 20px 0;
                }}
                #stream {{
                    max-width: 100%;
                    max-height: 70vh;
                    border-radius: 5px;
                }}
                .controls {{
                    text-align: center;
                    margin: 20px 0;
                }}
                button {{
                    padding: 10px 20px;
                    margin: 5px;
                    background: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                button:hover {{
                    background: #45a049;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📹 Веб-камера: {camera_name}</h1>
                
                <div class="info">
                    <p><strong>📡 Адрес:</strong> http://{hostname}.local:{port}</p>
                    <p><strong>🎬 Разрешение:</strong> {stream_res}</p>
                    <p><strong>⚡ FPS:</strong> {self.server.stream_fps}</p>
                </div>
                
                <div class="stream-container">
                    <img src="/stream.mjpg" id="stream">
                </div>
                
                <div class="controls">
                    <button onclick="location.reload()">🔄 Обновить</button>
                    <button onclick="captureSnapshot()">📸 Снимок</button>
                </div>
            </div>
            
            <script>
                const streamImg = document.getElementById('stream');
                
                streamImg.onerror = function() {{
                    setTimeout(() => {{
                        streamImg.src = '/stream.mjpg?t=' + Date.now();
                    }}, 1000);
                }};
                
                async function captureSnapshot() {{
                    try {{
                        const response = await fetch('/snapshot');
                        const blob = await response.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'snapshot_' + Date.now() + '.jpg';
                        a.click();
                    }} catch (error) {{
                        console.error('Ошибка:', error);
                    }}
                }}
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
    
    def capture_frame(self):
        """Захват кадра"""
        try:
            frame = self.server.capture_frame()
            if frame is not None:
                timestamp = int(time.time())
                filename = f"webcam_{timestamp}.jpg"
                filepath = os.path.join(self.server.save_dir, filename)
                
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, self.server.jpeg_quality])
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    "status": "success",
                    "filename": filename,
                    "resolution": f"{frame.shape[1]}x{frame.shape[0]}"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self.send_error(500, "Нет кадра")
        except Exception as e:
            self.send_error(500, f"Ошибка: {str(e)}")
    
    def send_status(self):
        """Статус сервера"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        status = {
            "camera": self.server.camera_name,
            "stream_resolution": f"{self.server.stream_width}x{self.server.stream_height}",
            "stream_fps": self.server.stream_fps,
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(status).encode('utf-8'))
    
    def send_snapshot(self):
        """Быстрый снимок"""
        try:
            frame = self.server.get_latest_frame()
            if frame is not None:
                ret, jpeg = cv2.imencode('.jpg', frame, 
                                        [cv2.IMWRITE_JPEG_QUALITY, self.server.stream_quality])
                if ret:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(jpeg))
                    self.end_headers()
                    self.wfile.write(jpeg.tobytes())
                else:
                    self.send_error(500, "Ошибка кодирования")
            else:
                self.send_error(500, "Нет кадра")
        except Exception as e:
            self.send_error(500, f"Ошибка: {str(e)}")

class WebcamStreamServer(HTTPServer):
    """Сервер для веб-камеры"""
    
    def __init__(self, server_address, webcam_capture, logger=None):
        super().__init__(server_address, WebcamStreamHandler)
        
        self.webcam = webcam_capture
        self.logger = logger
        
        # Параметры по умолчанию
        self.stream_width = 1280
        self.stream_height = 720
        self.stream_fps = 30
        self.stream_quality = 50
        self.camera_name = "Local Web Camera"
        self.save_dir = "./003_pics"
        self.jpeg_quality = 95
        
        # Технические параметры
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.streaming_active = True
        
        # Запускаем поток захвата
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
        
        if self.logger:
            self.logger.info(f"WebcamStreamServer запущен на порту {server_address[1]}")
    
    def capture_loop(self):
        """Цикл захвата кадров"""
        frame_interval = 1.0 / self.stream_fps
        
        while self.streaming_active:
            try:
                # Захват кадра
                frame = self.webcam.capture_frame()
                
                if frame is not None:
                    # Обновляем последний кадр
                    with self.frame_lock:
                        self.latest_frame = frame.copy()
                
                # Контроль FPS
                time.sleep(max(0, frame_interval))
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка захвата кадра: {e}")
                time.sleep(0.1)
    
    def get_latest_frame(self):
        """Получение последнего кадра"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None
    
    def capture_frame(self):
        """Захват кадра для сохранения"""
        return self.webcam.capture_frame()
    
    def stop_server(self):
        """Остановка сервера"""
        self.streaming_active = False
        self.shutdown()
        self.server_close()
        
        if self.logger:
            self.logger.info("WebcamStreamServer остановлен")

def main():
    """Основная функция"""
    print("📹 Запуск веб-камеры с MJPEG стримом")
    print("=" * 50)
    
    try:
        # Создаем логгер
        logger = create_logger('webcam')
        
        # Инициализируем веб-камеру
        print("📸 Инициализация веб-камеры...")
        webcam = WebcamCapture('local_web', debug=True)
        
        if not webcam.initialize():
            print("❌ Не удалось инициализировать веб-камеру")
            return
        
        print("✅ Веб-камера готова")
        
        # Создаем сервер
        print("🌐 Создание веб-сервера...")
        server_address = ('', 8081)
        server = WebcamStreamServer(server_address, webcam, logger)
        
        print("🚀 Запуск сервера...")
        print(f"📡 URL: http://localhost:8081")
        print(f"🎬 Стрим: http://localhost:8081/stream.mjpg")
        print(f"📸 Снимок: http://localhost:8081/capture")
        print("💡 Нажмите Ctrl+C для остановки")
        
        # Запускаем сервер
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Остановка...")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'server' in locals():
            server.stop_server()

if __name__ == "__main__":
    main()