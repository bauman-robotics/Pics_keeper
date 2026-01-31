#!/usr/bin/env python3
"""
Веб-сервер для стрима

Содержит классы StreamServer и StreamHandler для управления MJPEG стримом
с веб-интерфейсом, повторяя функциональность из исходного 01_pics_keeper.py.
"""

import cv2
import time
import threading
import socket
import json
import math
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Callable, Tuple, Dict, Any
from dataclasses import dataclass
from core.stream_settings import StreamStatus, StreamMetrics
from utils.logger import PicsKeeperLogger
import numpy as np

@dataclass
class StreamServerConfig:
    """Конфигурация веб-сервера стрима"""
    port: int = 8080
    stream_width: int = 1280
    stream_height: int = 720
    stream_fps: int = 30
    stream_quality: int = 50
    stream_analysis: bool = False
    low_latency: bool = True
    camera_name: str = "Unknown Camera"
    save_dir: str = "./003_pics"
    jpeg_quality: int = 95
    max_angle: float = 45.0
    warn_angle: float = 30.0
    force_capture: bool = False

class StreamHandler(SimpleHTTPRequestHandler):
    """Обработчик HTTP запросов для стрима"""
    
    def log_message(self, format, *args):
        if self.server.debug_mode:
            super().log_message(format, *args)
    
    def do_GET(self):
        """Обработка GET запросов"""
        
        if self.path == '/stream.mjpg':
            # MJPEG стрим с низкой задержкой
            self.send_low_latency_stream()
            
        elif self.path == '/':
            # Главная страница
            self.send_main_page()
            
        elif self.path == '/capture':
            # Захват кадра для сохранения
            self.capture_frame_for_saving()
            
        elif self.path == '/status':
            # Статус сервера
            self.send_status()
            
        elif self.path == '/snapshot':
            # Быстрый снимок
            self.send_snapshot()
            
        else:
            super().do_GET()
    
    def send_low_latency_stream(self):
        """Отправка MJPEG стрима с минимальной задержкой"""
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
                
                # Контроль FPS - пропускаем кадры если отстаем
                current_time = time.time()
                if current_time - last_frame_time < 1.0 / self.server.stream_fps:
                    time.sleep(0.001)
                    continue
                
                # Получаем самый свежий кадр из очереди
                frame = self.server.get_latest_frame()
                
                if frame is not None and frame.size > 0:
                    # Применяем анализ только если включен
                    if self.server.stream_analysis:
                        frame = self.server.analyze_frame(frame)
                    
                    # Конвертируем в RGB для веб-страницы
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Кодируем в JPEG
                    encode_start = time.time()
                    ret, jpeg = cv2.imencode('.jpg', frame_rgb, 
                                            [cv2.IMWRITE_JPEG_QUALITY, self.server.stream_quality])
                    
                    if ret:
                        # Отправляем кадр
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(jpeg))
                        self.end_headers()
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        
                        # Статистика
                        frame_count += 1
                        current_time = time.time()
                        frame_latency = current_time - start_time
                        total_latency += frame_latency
                        last_frame_time = current_time
                        
                        # Вывод статистики каждые 5 секунд
                        if current_time - last_stats_time >= 5:
                            avg_latency = total_latency / frame_count
                            fps = frame_count / 5
                            
                            if self.server.debug_mode:
                                print(f"📊 Стрим: {fps:.1f} FPS, Задержка: {avg_latency*1000:.0f} мс")
                            
                            frame_count = 0
                            total_latency = 0
                            last_stats_time = current_time
                else:
                    # Нет кадра, небольшая пауза
                    time.sleep(0.01)
                        
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as e:
            if self.server.debug_mode:
                print(f"🔌 Отключение от стрима: {e}")
        except Exception as e:
            if self.server.debug_mode:
                print(f"❌ Ошибка стрима: {e}")
    
    def send_main_page(self):
        """Отправка главной страницы"""
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
        """Захват кадра для сохранения (использует разрешение съемки)"""
        try:
            # Получаем кадр в разрешении съемки
            frame = self.server.capture_high_res_frame()
            
            if frame is not None and frame.size > 0:
                # Конвертируем кадр из BGR (OpenCV) в RGB для анализа
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)                
                
                timestamp = int(time.time())
                
                # Находим следующий номер
                existing_files = [f for f in os.listdir(self.server.save_dir) 
                                if f.startswith('chessboard_') and f.endswith('.jpg')]
                
                # Ищем максимальный номер среди существующих файлов
                max_number = 0
                for file in existing_files:
                    try:
                        # Ищем файлы в формате chessboard_001_1769460969.jpg
                        parts = file.split('_')
                        if len(parts) >= 2:
                            # Пробуем извлечь номер из второй части
                            number_str = parts[1]
                            if number_str.isdigit():
                                number = int(number_str)
                                max_number = max(max_number, number)
                    except:
                        continue
                
                next_number = max_number + 1
                
                # Создаем имя файла
                filename = f"chessboard_{next_number:03d}_{timestamp}.jpg"
                filepath = os.path.join(self.server.save_dir, filename)
                
                # Проверяем угол если анализ включен
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
                
                # Сохраняем с высоким качеством (OpenCV использует BGR)
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
        """Отправка статуса"""
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
        """Быстрый снимок в разрешении стрима"""
        try:
            frame = self.server.get_latest_frame()
            if frame is not None and frame.size > 0:
                # Конвертируем в RGB для веб-страницы
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

class StreamServer(HTTPServer):
    """Веб-сервер для MJPEG стрима"""
    
    def __init__(
        self, 
        config: StreamServerConfig,
        frame_source: Optional[Callable[[], Optional[np.ndarray]]] = None,
        logger: Optional[PicsKeeperLogger] = None
    ):
        """
        Инициализация веб-сервера стрима
        
        Args:
            config: Конфигурация сервера
            frame_source: Функция для получения кадров
            logger: Система логирования
        """
        server_address = ('', config.port)
        super().__init__(server_address, StreamHandler)
        
        self.config = config
        self.logger = logger
        self.frame_source = frame_source
        
        # Параметры стрима
        self.stream_width = config.stream_width
        self.stream_height = config.stream_height
        self.stream_fps = config.stream_fps
        self.stream_quality = config.stream_quality
        self.stream_analysis = config.stream_analysis
        self.low_latency = config.low_latency
        
        # Параметры съемки
        self.save_dir = config.save_dir
        self.jpeg_quality = config.jpeg_quality
        self.max_angle = config.max_angle
        self.warn_angle = config.warn_angle
        self.force_capture = config.force_capture
        
        # Технические параметры
        self.debug_mode = getattr(logger, 'debug_mode', False) if logger else False
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.streaming_active = True
        
        # Атрибуты для веб-интерфейса
        self.camera_name = config.camera_name
        self.save_dir = config.save_dir
        self.jpeg_quality = config.jpeg_quality
        self.max_angle = config.max_angle
        self.warn_angle = config.warn_angle
        self.force_capture = config.force_capture
        
        # Метрики
        self._metrics = StreamMetrics(
            total_frames=0,
            dropped_frames=0,
            avg_fps=0.0,
            min_fps=float('inf'),
            max_fps=0.0
        )
        
        if self.logger:
            self.logger.info(f"StreamServer инициализирован на порту {config.port}")
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Получение самого свежего кадра"""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None
    
    def set_frame_source(self, frame_source: Callable[[], Optional[np.ndarray]]):
        """Установка источника кадров"""
        self.frame_source = frame_source
    
    def update_frame(self, frame: np.ndarray):
        """Обновление текущего кадра"""
        with self.frame_lock:
            self.latest_frame = frame.copy()
    
    def capture_high_res_frame(self) -> Optional[np.ndarray]:
        """Захват кадра в высоком разрешении для сохранения"""
        if self.frame_source:
            return self.frame_source()
        return None
    
    def analyze_frame(self, frame: np.ndarray) -> np.ndarray:
        """Анализ кадра (если включен)"""
        if not self.stream_analysis or frame is None:
            return frame
        
        try:
            # Быстрый анализ только углов
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            chessboard_size = (7, 7)
            
            ret, corners = cv2.findChessboardCorners(
                gray, chessboard_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK
            )
            
            if ret:
                # Рисуем углы
                cv2.drawChessboardCorners(frame, chessboard_size, corners, ret)
                
                # Быстрая оценка угла
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
                    
                    # Индикатор угла
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
    
    def analyze_chessboard_angle(self, frame: np.ndarray) -> Dict[str, Any]:
        """Анализ угла шахматной доски"""
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
    
    def get_status(self) -> StreamStatus:
        """Получение статуса сервера"""
        return StreamStatus(
            fps=self._metrics.avg_fps,
            resolution=(self.stream_width, self.stream_height),
            stream_enabled=self.streaming_active,
            low_latency=self.low_latency,
            timestamp=time.time()
        )
    
    def get_metrics(self) -> StreamMetrics:
        """Получение метрик производительности"""
        return self._metrics
    
    def start_server(self):
        """Запуск сервера в отдельном потоке"""
        server_thread = threading.Thread(target=self.serve_forever, daemon=True)
        server_thread.start()
        
        if self.logger:
            self.logger.info(f"StreamServer запущен на порту {self.server_port}")
        
        return server_thread
    
    def stop_server(self):
        """Остановка сервера"""
        self.streaming_active = False
        self.shutdown()
        self.server_close()
        
        if self.logger:
            self.logger.info("StreamServer остановлен")