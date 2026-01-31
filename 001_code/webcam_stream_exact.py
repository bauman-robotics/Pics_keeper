#!/usr/bin/env python3
"""
Точный перенос MJPEG стрима из 01_pics_keeper.py для веб-камеры

Повторяет рабочий код дословно, но адаптирован для веб-камеры.
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

class ExactWebcamStreamHandler(SimpleHTTPRequestHandler):
    """Обработчик HTTP запросов - точная копия из 01_pics_keeper.py"""
    
    def log_message(self, format, *args):
        if self.server.debug_mode:
            super().log_message(format, *args)
    
    def do_GET(self):
        """Обработка GET запросов - точная копия"""
        
        if self.path == '/stream.mjpg':
            # MJPEG стрим с низкой задержкой - ТОЧНАЯ КОПИЯ
            self.send_low_latency_stream()
            
        elif self.path == '/':
            # Главная страница - ТОЧНАЯ КОПИЯ
            self.send_main_page()
            
        elif self.path == '/capture':
            # Захват кадра для сохранения - ТОЧНАЯ КОПИЯ
            self.capture_frame_for_saving()
            
        elif self.path == '/status':
            # Статус сервера - ТОЧНАЯ КОПИЯ
            self.send_status()
            
        elif self.path == '/snapshot':
            # Быстрый снимок - ТОЧНАЯ КОПИЯ
            self.send_snapshot()
            
        else:
            super().do_GET()
    
    def send_low_latency_stream(self):
        """Отправка MJPEG стрима с минимальной задержкой - ТОЧНАЯ КОПИЯ"""
        client_ip = self.client_address[0]
        if self.server.debug_mode:
            print(f"🔄 Подключение к стриму от {client_ip}")
        
        self.send_response(200)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        
        try:
            frame_count = 0
            last_stats_time = time.time()
            last_frame_time = time.time()
            total_latency = 0
            skip_frames = 0  # Счетчик пропущенных кадров
            
            while True:
                start_time = time.time()
                
                # Контроль FPS - пропускаем кадры если отстаем - ТОЧНАЯ КОПИЯ
                current_time = time.time()
                if current_time - last_frame_time < 1.0 / self.server.stream_fps:
                    time.sleep(0.001)
                    continue
                
                # Получаем самый свежий кадр из очереди - ТОЧНАЯ КОПИЯ
                frame = self.server.get_latest_frame()
                
                if frame is not None and frame.size > 0:
                    # Применяем анализ только если включен - ТОЧНАЯ КОПИЯ
                    if self.server.stream_analysis:
                        frame = self.server.analyze_frame(frame)
                    
                    # Конвертируем в RGB для веб-страницы - ТОЧНАЯ КОПИЯ
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Кодируем в JPEG - ТОЧНАЯ КОПИЯ
                    encode_start = time.time()
                    ret, jpeg = cv2.imencode('.jpg', frame_rgb, 
                                            [cv2.IMWRITE_JPEG_QUALITY, self.server.stream_quality])
                    
                    if ret:
                        # Отправляем кадр - ТОЧНАЯ КОПИЯ
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(jpeg))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        
                        # Статистика - ТОЧНАЯ КОПИЯ
                        frame_count += 1
                        current_time = time.time()
                        frame_latency = current_time - start_time
                        total_latency += frame_latency
                        last_frame_time = current_time
                        
                        # Вывод статистики каждые 5 секунд - ТОЧНАЯ КОПИЯ
                        if current_time - last_stats_time >= 5:
                            avg_latency = total_latency / frame_count
                            fps = frame_count / 5
                            
                            if self.server.debug_mode:
                                print(f"📊 Стрим: {fps:.1f} FPS, Задержка: {avg_latency*1000:.0f} мс")
                            
                            frame_count = 0
                            total_latency = 0
                            last_stats_time = current_time
                else:
                    # Нет кадра, небольшая пауза - ТОЧНАЯ КОПИЯ
                    time.sleep(0.01)
                        
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
            if self.server.debug_mode:
                print(f"🔌 Отключение от стрима: {e}")
        except Exception as e:
            if self.server.debug_mode:
                print(f"❌ Ошибка стрима: {e}")
    
    def send_main_page(self):
        """Отправка главной страницы - ТОЧНАЯ КОПИЯ"""
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
            <title>Стрим камеры {camera_name}</title>
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
                
                .stats {{
                    background: #2a2a2a;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                    font-family: monospace;
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
                <h1>📷 Стрим камеры: {camera_name}</h1>
                
                <div class="info">
                    <p><strong>📡 Адрес:</strong> http://{hostname}.local:{port}</p>
                    <p><strong>🎬 Разрешение:</strong> {stream_res}</p>
                    <p><strong>⚡ FPS:</strong> {self.server.stream_fps}</p>
                    <p><strong>🔍 Анализ:</strong> {'ВКЛ' if self.server.stream_analysis else 'ВЫКЛ'}</p>
                </div>
                
                <div class="stream-container">
                    <img src="/stream.mjpg" id="stream">
                </div>
                
                <div class="stats" id="stats">
                    Загрузка...
                </div>
                
                <div class="controls">
                    <button onclick="location.reload()">🔄 Обновить</button>
                    <button onclick="captureSnapshot()">📸 Снимок</button>
                    <button onclick="toggleFullscreen()">📺 Полный экран</button>
                </div>
            </div>
            
            <script>
                let frameCount = 0;
                let lastTime = Date.now();
                
                const streamImg = document.getElementById('stream');
                const statsDiv = document.getElementById('stats');
                
                // Обновление статистики
                function updateStats() {{
                    const now = Date.now();
                    frameCount++;
                    
                    if (now - lastTime >= 1000) {{
                        const fps = Math.round((frameCount * 1000) / (now - lastTime));
                        statsDiv.innerHTML = `FPS: ${{fps}} | Размер: {stream_res}`;
                        frameCount = 0;
                        lastTime = now;
                    }}
                    
                    setTimeout(updateStats, 100);
                }}
                
                // Автоподключение
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
                
                function toggleFullscreen() {{
                    if (!document.fullscreenElement) {{
                        document.documentElement.requestFullscreen();
                    }} else {{
                        document.exitFullscreen();
                    }}
                }}
                
                // Запуск
                updateStats();
                
                // Автообновление каждые 5 минут
                setTimeout(() => location.reload(), 300000);
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
    
    def capture_frame_for_saving(self):
        """Захват кадра для сохранения - ТОЧНАЯ КОПИЯ"""
        try:
            # Получаем кадр в разрешении съемки - ТОЧНАЯ КОПИЯ
            frame = self.server.capture_high_res_frame()
            
            if frame is not None and frame.size > 0:
                # Конвертируем кадр из BGR (OpenCV) в RGB для анализа - ТОЧНАЯ КОПИЯ
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)                
                
                timestamp = int(time.time())
                
                # Находим следующий номер - ТОЧНАЯ КОПИЯ
                existing_files = [f for f in os.listdir(self.server.save_dir) 
                                if f.startswith('chessboard_') and f.endswith('.jpg')]
                
                # Ищем максимальный номер среди существующих файлов - ТОЧНАЯ КОПИЯ
                max_number = 0
                for file in existing_files:
                    try:
                        # Ищем файлы в формате chessboard_001_1769460969.jpg - ТОЧНАЯ КОПИЯ
                        parts = file.split('_')
                        if len(parts) >= 2:
                            # Пробуем извлечь номер из второй части - ТОЧНАЯ КОПИЯ
                            number_str = parts[1]
                            if number_str.isdigit():
                                number = int(number_str)
                                max_number = max(max_number, number)
                    except:
                        continue
                
                next_number = max_number + 1
                
                # Создаем имя файла - ТОЧНАЯ КОПИЯ
                filename = f"chessboard_{next_number:03d}_{timestamp}.jpg"
                filepath = os.path.join(self.server.save_dir, filename)
                
                # Проверяем угол если анализ включен - ТОЧНАЯ КОПИЯ
                if self.server.stream_analysis:
                    analysis = self.server.analyze_chessboard_angle(frame)
                    if analysis and analysis['found']:
                        if analysis['angle_deviation'] > self.server.max_angle and not self.server.force_capture:
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            response = {
                                "error": "angle_too_large",
                                "angle": analysis['angle_deviation']
                            }
                            self.wfile.write(json.dumps(response).encode('utf-8'))
                            return
                
                # Сохраняем с высоким качеством (OpenCV использует BGR) - ТОЧНАЯ КОПИЯ
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
        """Отправка статуса - ТОЧНАЯ КОПИЯ"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        status = {
            "camera": self.server.camera_name,
            "stream_resolution": f"{self.server.stream_width}x{self.server.stream_height}",
            "stream_fps": self.server.stream_fps,
            "stream_quality": self.server.stream_quality,
            "stream_analysis": self.server.stream_analysis,
            "low_latency": self.server.low_latency,
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(status).encode('utf-8'))
    
    def send_snapshot(self):
        """Быстрый снимок в разрешении стрима - ТОЧНАЯ КОПИЯ"""
        try:
            frame = self.server.get_latest_frame()
            if frame is not None and frame.size > 0:
                # Конвертируем в RGB для веб-страницы - ТОЧНАЯ КОПИЯ
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ret, jpeg = cv2.imencode('.jpg', frame_rgb, 
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

class ExactWebcamStreamServer(HTTPServer):
    """Сервер стрима с низкой задержкой - ТОЧНАЯ КОПИЯ"""
    
    def __init__(self, server_address, webcam_capture, logger=None):
        super().__init__(server_address, ExactWebcamStreamHandler)
        
        self.webcam = webcam_capture
        self.logger = logger
        
        # Параметры стрима (отдельные от съемки!) - ТОЧНАЯ КОПИЯ
        self.stream_width = 1280
        self.stream_height = 720
        self.stream_fps = 30
        self.stream_quality = 50
        self.stream_analysis = False
        self.low_latency = True
        
        # Параметры съемки - ТОЧНАЯ КОПИЯ
        self.save_dir = "./003_pics"
        self.jpeg_quality = 95
        self.max_angle = 45.0
        self.warn_angle = 30.0
        self.force_capture = False
        
        # Технические параметры - ТОЧНАЯ КОПИЯ
        self.debug_mode = getattr(logger, 'debug_mode', False) if logger else False
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.streaming_active = True
        
        # Атрибуты для веб-интерфейса - ТОЧНАЯ КОПИЯ
        self.camera_name = "Local Web Camera"
        self.save_dir = "./003_pics"
        self.jpeg_quality = 95
        self.max_angle = 45.0
        self.warn_angle = 30.0
        self.force_capture = False
        
        # Запускаем поток захвата кадров - ТОЧНАЯ КОПИЯ
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
        
        if self.logger:
            self.logger.info(f"ExactWebcamStreamServer запущен на порту {server_address[1]}")
    
    def capture_loop(self):
        """Цикл захвата кадров - ТОЧНАЯ КОПИЯ"""
        frame_interval = 1.0 / self.stream_fps
        
        while self.streaming_active:
            try:
                # Захват кадра - ТОЧНАЯ КОПИЯ
                frame = self.webcam.capture_frame()
                
                if frame is not None and frame.size > 0:
                    # Обновляем последний кадр - ТОЧНАЯ КОПИЯ
                    with self.frame_lock:
                        self.latest_frame = frame.copy()
                
                # Контроль FPS - ТОЧНАЯ КОПИЯ
                current_time = time.time()
                if current_time - getattr(self, '_last_frame_time', 0) < frame_interval:
                    time.sleep(0.001)
                    continue
                
                self._last_frame_time = current_time
                
            except Exception as e:
                if self.debug_mode:
                    print(f"❌ Ошибка захвата кадра: {e}")
                time.sleep(0.1)
    
    def get_latest_frame(self):
        """Получение самого свежего кадра - ТОЧНАЯ КОПИЯ"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None
    
    def capture_high_res_frame(self):
        """Захват кадра в высоком разрешении для сохранения - ТОЧНАЯ КОПИЯ"""
        try:
            # Останавливаем стрим на время захвата высокого разрешения - ТОЧНАЯ КОПИЯ
            self.streaming_active = False
            time.sleep(0.1)  # Даем время остановиться
            
            # Захват кадра - ТОЧНАЯ КОПИЯ
            frame = self.webcam.capture_frame()
            
            # Возвращаемся к стриму - ТОЧНАЯ КОПИЯ
            self.streaming_active = True
            
            return frame
            
        except Exception as e:
            print(f"❌ Ошибка захвата высокого разрешения: {e}")
            self.streaming_active = True
            return None
    
    def analyze_frame(self, frame):
        """Анализ кадра (если включен) - ТОЧНАЯ КОПИЯ"""
        if not self.stream_analysis or frame is None:
            return frame
        
        try:
            # Быстрый анализ только углов - ТОЧНАЯ КОПИЯ
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            chessboard_size = (7, 7)
            
            ret, corners = cv2.findChessboardCorners(
                gray, chessboard_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK
            )
            
            if ret:
                # Рисуем углы - ТОЧНАЯ КОПИЯ
                cv2.drawChessboardCorners(frame, chessboard_size, corners, ret)
                
                # Быстрая оценка угла - ТОЧНАЯ КОПИЯ
                if len(corners) >= 49:
                    corners = corners.reshape(7, 7, 2)
                    tl = corners[0, 0]
                    tr = corners[0, -1]
                    bl = corners[-1, 0]
                    
                    top_vec = tr - tl
                    left_vec = bl - tl
                    
                    angle_h = math.degrees(math.atan2(top_vec[1], top_vec[0]))
                    angle_v = math.degrees(math.atan2(left_vec[1], left_vec[0]))
                    angle_dev = min(abs(angle_h), abs(90 - angle_v))
                    
                    # Индикатор угла - ТОЧНАЯ КОПИЯ
                    color = (0, 255, 0)  # зеленый
                    if angle_dev > self.warn_angle:
                        color = (0, 255, 255)  # желтый
                    if angle_dev > self.max_angle:
                        color = (0, 0, 255)  # красный
                    
                    cv2.putText(frame, f"Angle: {angle_dev:.1f} deg", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            return frame
            
        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Ошибка анализа: {e}")
            return frame
    
    def analyze_chessboard_angle(self, frame):
        """Анализ угла шахматной доски - ТОЧНАЯ КОПИЯ"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            chessboard_size = (7, 7)
            
            ret, corners = cv2.findChessboardCorners(
                gray, chessboard_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            )
            
            if ret:
                corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                          (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                
                corners = corners.reshape(7, 7, 2)
                tl = corners[0, 0]
                tr = corners[0, -1]
                bl = corners[-1, 0]
                
                top_vec = tr - tl
                left_vec = bl - tl
                
                angle_h = math.degrees(math.atan2(top_vec[1], top_vec[0]))
                angle_v = math.degrees(math.atan2(left_vec[1], left_vec[0]))
                angle_dev = min(abs(angle_h), abs(90 - angle_v))
                
                return {
                    'found': True,
                    'angle_deviation': angle_dev
                }
                
        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Ошибка анализа угла: {e}")
        
        return {'found': False}
    
    def stop_server(self):
        """Остановка сервера - ТОЧНАЯ КОПИЯ"""
        self.streaming_active = False
        self.shutdown()
        self.server_close()
        
        if self.logger:
            self.logger.info("ExactWebcamStreamServer остановлен")

def main():
    """Основная функция - ТОЧНАЯ КОПИЯ"""
    print("📹 Запуск веб-камеры с MJPEG стримом (точная копия)")
    print("=" * 70)
    
    try:
        # Создаем логгер - ТОЧНАЯ КОПИЯ
        logger = create_logger('webcam')
        
        # Инициализируем веб-камеру - ТОЧНАЯ КОПИЯ
        print("📸 Инициализация веб-камеры...")
        webcam = WebcamCapture('local_web', debug=True)
        
        if not webcam.initialize():
            print("❌ Не удалось инициализировать веб-камеру")
            return
        
        print("✅ Веб-камера готова")
        
        # Создаем сервер - ТОЧНАЯ КОПИЯ
        print("🌐 Создание веб-сервера...")
        server_address = ('', 8081)
        server = ExactWebcamStreamServer(server_address, webcam, logger)
        
        print("🚀 Запуск сервера...")
        print(f"📡 URL: http://localhost:8081")
        print(f"🎬 Стрим: http://localhost:8081/stream.mjpg")
        print(f"📸 Снимок: http://localhost:8081/capture")
        print("💡 Нажмите Ctrl+C для остановки")
        print("⚡ Режим низкой задержки включен")
        
        # Запускаем сервер - ТОЧНАЯ КОПИЯ
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