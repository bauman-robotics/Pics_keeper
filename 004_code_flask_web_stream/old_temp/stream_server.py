#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import os
import threading
import time

PORT = 8080
FRAME_FILE = "/tmp/cam_frame.jpg"
stop_flag = False

def capture_frames():
    """Фоновая задача для захвата кадров"""
    global stop_flag
    while not stop_flag:
        try:
            # Захватываем кадр
            result = subprocess.run([
                'ffmpeg',
                '-f', 'v4l2',
                '-i', '/dev/video0',
                '-frames:v', '1',
                '-vf', 'scale=640:480',
                '-q:v', '2',
                '-y', FRAME_FILE
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            
            if result.returncode != 0:
                print("⚠️ Ошибка захвата кадра")
            
            time.sleep(0.1)  # 10 FPS
        except Exception as e:
            print(f"⚠️ Исключение в capture_frames: {e}")
            time.sleep(1)

class CamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Минимальное логирование
        pass
    
    def do_GET(self):
        if self.path == '/':
            # Отдаем HTML
            html = '''<!DOCTYPE html>
<html>
<head>
    <title>🎥 Камера</title>
    <meta charset="utf-8">
    <style>
        body {
            margin: 0;
            padding: 20px;
            text-align: center;
            font-family: Arial;
            background: #f0f0f0;
        }
        .container {
            display: inline-block;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        img {
            border: 2px solid #333;
            border-radius: 5px;
            background: black;
        }
        .status {
            margin: 10px;
            padding: 10px;
            background: #e0e0e0;
            border-radius: 5px;
        }
    </style>
    <script>
        let count = 0;
        function update() {
            const img = document.getElementById('stream');
            const counter = document.getElementById('counter');
            
            img.onload = function() {
                count++;
                counter.textContent = 'Кадров: ' + count;
                setTimeout(update, 100);
            };
            
            img.onerror = function() {
                console.log('Ошибка загрузки');
                setTimeout(update, 1000);
            };
            
            img.src = '/stream?t=' + Date.now();
        }
        window.onload = update;
    </script>
</head>
<body>
    <div class="container">
        <h1>Веб-камера /dev/video0</h1>
        <img id="stream" width="640" height="480" alt="Камера">
        <div id="counter" class="status">Загрузка...</div>
    </div>
</body>
</html>'''
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        elif self.path.startswith('/stream'):
            # Отдаем последний захваченный кадр
            if os.path.exists(FRAME_FILE):
                try:
                    with open(FRAME_FILE, 'rb') as f:
                        data = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(data)
                except Exception as e:
                    print(f"Ошибка чтения файла: {e}")
                    self.send_error(500)
            else:
                # Если файла нет, делаем снимок на лету
                try:
                    subprocess.run([
                        'ffmpeg',
                        '-f', 'v4l2',
                        '-i', '/dev/video0',
                        '-frames:v', '1',
                        '-vf', 'scale=640:480',
                        '-q:v', '2',
                        '-y', FRAME_FILE
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                    
                    if os.path.exists(FRAME_FILE):
                        with open(FRAME_FILE, 'rb') as f:
                            data = f.read()
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.wfile.write(data)
                    else:
                        self.send_error(404)
                except:
                    self.send_error(500)

def main():
    global stop_flag
    
    print("=" * 50)
    print("🎬 Запуск сервера веб-камеры")
    print("=" * 50)
    
    # Проверяем камеру
    print("🔍 Проверяем камеру...")
    test = subprocess.run(['ffmpeg', '-f', 'v4l2', '-i', '/dev/video0', '-t', '1', '-f', 'null', '-'], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if test.returncode != 0:
        print("❌ Камера не доступна!")
        print("Проверьте: ffplay -f v4l2 -i /dev/video0")
        return
    
    print("✅ Камера доступна")
    
    # Запускаем фоновый захват кадров
    print("🚀 Запускаем захват кадров...")
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    
    # Запускаем HTTP сервер
    print(f"🌐 HTTP сервер: http://localhost:{PORT}")
    print("📱 Откройте в браузере")
    print("🛑 Ctrl+C для остановки")
    print("=" * 50)
    
    try:
        server = HTTPServer(('', PORT), CamHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Останавливаем сервер...")
        stop_flag = True
        capture_thread.join(timeout=2)
        print("👋 Сервер остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        stop_flag = True

if __name__ == '__main__':
    main()