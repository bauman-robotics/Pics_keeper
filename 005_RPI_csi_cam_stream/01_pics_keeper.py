#!/usr/bin/env python3

'''
file_name: 01_pics_keeper.py
old_name: /home/pi/projects/Hailo8_projects/cam_calibr/49_get_calbr_data_full_size_Ok.py

rpicam-still --list-cameras

python3 01_pics_keeper.py --debug --stream-fps 25 --no-analysis --delay 3
python3 01_pics_keeper.py 
# ======
export DISPLAY=:0

1. убить сессию:
screen -X -S bird_detector quit

2. активация вирт окружения
source /home/pi/projects/Hailo8_projects/Hailo-8/16__hailort_v4.23.0/hailo_runtime_env/bin/activate

# ======
IMX708 (Camera Module 3):
✅ LensPosition поддерживается: Можно менять от 0.0 до 1.0
✅ FocusFoM работает: Показывает метрику резкости (273-283)
✅ AfMode, AfRange поддерживаются: Но это фиктивный автофокус
❌ AfEnable не поддерживается: Нет настоящего автофокуса

IMX415:
✅ FocusFoM работает: Показывает метрику резкости (2612)
❌ LensPosition не поддерживается: Фиксированный фокус
❌ AfEnable не поддерживается: Нет управления фокусом
'''

'''
deactivate
source /home/pi/projects/Hailo8_projects/cam_calibr/venv/bin/activate
cd /home/pi/projects/Hailo8_projects/Pics_keeper/005_RPI_csi_cam_stream

python3 01_pics_keeper.py

http://localhost:8080
'''


import os
import time
import argparse
import threading
import socket
import sys
import json
import math
import queue
from collections import deque
from http.server import HTTPServer, SimpleHTTPRequestHandler
from picamera2 import Picamera2
import cv2
import numpy as np
import random 

# ===========================================
# КОНСТАНТЫ И НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ===========================================

full_resolution_IMX708_w = 4608
full_resolution_IMX708_h = 2592

full_resolution_IMX415_w = 3864
full_resolution_IMX415_h = 2192

# ПАРАМЕТРЫ КАМЕР
CAMERA_PROFILES = {
    'imx708': {
        'name': 'IMX708 (RPi Camera Module 3)',
        'full_resolution': (full_resolution_IMX708_w, full_resolution_IMX708_h),
        'sensor_size': (4.55, 3.42),
        'pixel_size': 1.0,
        'focal_length': 3.04,
    },
    'imx415': {
        'name': 'Sony IMX415',
        'full_resolution': (full_resolution_IMX415_w, full_resolution_IMX415_h),        
        'sensor_size': (5.568, 3.132),
        'pixel_size': 1.45,
        'focal_length': 3.95,
    },
    'ov5647': {
        'name': 'OV5647 (RPi Camera Module v1/v2)',
        'full_resolution': (2592, 1944),
        'sensor_size': (3.68, 2.76),
        'pixel_size': 1.4,
        'focal_length': 3.6,
    }
}

# ПАРАМЕТРЫ ПО УМОЛЧАНИЮ
#DEFAULT_CAMERA_TYPE = 'imx415'  # imx708 -0    imx415 -1    ov5647
DEFAULT_CAMERA_TYPE = 'imx708'

#STREAM_TYPE = 'full_resolution'
STREAM_TYPE = '1280x720'
#STREAM_TYPE = '640x480'


if STREAM_TYPE == 'full_resolution':
    if DEFAULT_CAMERA_TYPE == 'imx415':
        DEFAULT_STREAM_WIDTH = full_resolution_IMX415_w           # Ширина стрима по умолчанию  imx415
        DEFAULT_STREAM_HEIGHT = full_resolution_IMX415_h           # Высота стрима по умолчанию
    else: 
        DEFAULT_STREAM_WIDTH = full_resolution_IMX708_w           # Ширина стрима по умолчанию  imx708
        DEFAULT_STREAM_HEIGHT = full_resolution_IMX708_h           # Высота стрима по умолчанию  
elif STREAM_TYPE == '1280x720':
    DEFAULT_STREAM_WIDTH = 1280           # Ширина стрима по умолчанию
    DEFAULT_STREAM_HEIGHT = 720           # Высота стрима по умолчанию 
elif STREAM_TYPE == '640x480':
    DEFAULT_STREAM_WIDTH = 640           # Ширина стрима по умолчанию
    DEFAULT_STREAM_HEIGHT = 480           # Высота стрима по умолчанию   
    
DEFAULT_RESOLUTION = 'full'           # 'full' или 'stream'

DEFAULT_STREAM_ENABLED = True
DEFAULT_STREAM_PORT = 8080
DEFAULT_STREAM_FPS = 30               # Выше FPS для меньшей задержки
DEFAULT_STREAM_QUALITY = 50
DEFAULT_STREAM_ANALYSIS = False       # Отключить анализ по умолчанию для скорости
DEFAULT_STREAM_LOW_LATENCY = True     # Режим низкой задержки

# ПАРАМЕТРЫ СЪЕМКИ
DEFAULT_DELAY = 0
DEFAULT_COUNT = 20
DEFAULT_OUTPUT_DIR = 'calibration_images'
DEFAULT_JPEG_QUALITY = 95

# ПАРАМЕТРЫ КОНТРОЛЯ УГЛОВ (только для съемки)
MAX_ACCEPTABLE_ANGLE = 45
WARNING_ANGLE = 30
ASPECT_RATIO_TOLERANCE = 0.15

# ПАРАМЕТРЫ ПРЕДПРОСМОТРА
DEFAULT_PREVIEW_ENABLED = False

# ПАРАМЕТРЫ ЭКСПОЗИЦИИ ПО УМОЛЧАНИЮ
DEFAULT_EXPOSURE_TIME = 40000         # Выдержка в микросекундах (40ms)
DEFAULT_ANALOGUE_GAIN = 2.0           # Аналоговое усиление
DEFAULT_DIGITAL_GAIN = 1.0            # Цифровое усиление
DEFAULT_AE_ENABLE = False             # Автоэкспозиция для съемки (False=выкл)
DEFAULT_AWB_ENABLE = True             # Автобаланс белого
DEFAULT_NOISE_REDUCTION_MODE = 2      # Режим шумоподавления (2=высокое качество)

# ПАРАМЕТРЫ ФОКУСИРОВКИ ПО УМОЛЧАНИЮ
DEFAULT_AF_ENABLE = False # True #False             # Автофокус (False=выкл для калибровки)
DEFAULT_LENS_POSITION = 0.5           # Позиция линзы (1.0=бесконечность для IMX415)
#DEFAULT_LENS_POSITION = 0.0           # Позиция линзы (0.0=  только для IMX415)
#DEFAULT_AF_MODE = 0                   # Режим автофокуса
DEFAULT_AF_MODE = 0                   # Режим автофокуса
DEFAULT_AF_RANGE = 0                  # Диапазон фокусировки

# ПАРАМЕТРЫ СТРИМА (ЭКСПОЗИЦИЯ)
DEFAULT_STREAM_AE_ENABLE = True       # Автоэкспозиция для стрима (True=вкл)
DEFAULT_STREAM_EXPOSURE_TIME = 40000  # Стартовая выдержка для стрима
DEFAULT_STREAM_ANALOGUE_GAIN = 2.0    # Стартовое усиление для стрима
DEFAULT_STREAM_NOISE_REDUCTION = 1    # Режим шумоподавления для стрима (1=быстрый)

# ===========================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ОБМЕНА ДАННЫМИ
# ===========================================

global_stream_server = None
global_picam2 = None
global_camera_info = None
global_capture_size = None
global_save_dir = None

# ===========================================
# ПАРСИНГ АРГУМЕНТОВ КОМАНДНОЙ СТРОКИ
# ===========================================

parser = argparse.ArgumentParser(
    description='Калибровка камер Raspberry Pi с отдельными настройками стрима',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Примеры использования:
  %(prog)s                                           # IMX708, стрим 1280x720 без анализа
  %(prog)s --camera imx708 --stream-width 640 --stream-height 480
  %(prog)s --no-analysis --stream-fps 60             # Макс. FPS, без анализа
  %(prog)s --stream-analysis --max-angle 30          # С анализом, контроль углов
  %(prog)s --no-stream                               # Без стрима
  %(prog)s --stream-width 1920 --stream-height 1080  # Full HD стрим
"""
)

# Группа параметров камеры
camera_group = parser.add_argument_group('Параметры камеры')
camera_group.add_argument('--camera', type=str, default=DEFAULT_CAMERA_TYPE,
                         choices=['imx708', 'imx415', 'ov5647'],
                         help=f'Тип камеры (по умолчанию: {DEFAULT_CAMERA_TYPE})')
camera_group.add_argument('--resolution', type=str, default=DEFAULT_RESOLUTION,
                         choices=['full', 'stream'],
                         help=f'Разрешение съемки: full=полное, stream=стримовое (по умолчанию: {DEFAULT_RESOLUTION})')

# Группа параметров стрима (ОТДЕЛЬНО!)
stream_group = parser.add_argument_group('Параметры стрима (не влияют на съемку)')
stream_group.add_argument('--stream-width', type=int, default=DEFAULT_STREAM_WIDTH,
                         help=f'Ширина стрима (по умолчанию: {DEFAULT_STREAM_WIDTH})')
stream_group.add_argument('--stream-height', type=int, default=DEFAULT_STREAM_HEIGHT,
                         help=f'Высота стрима (по умолчанию: {DEFAULT_STREAM_HEIGHT})')
stream_group.add_argument('--stream', action='store_true', default=DEFAULT_STREAM_ENABLED,
                         help='Включить стрим (по умолчанию: ВКЛЮЧЕН)')
stream_group.add_argument('--no-stream', action='store_false', dest='stream',
                         help='Выключить стрим')
stream_group.add_argument('--stream-port', type=int, default=DEFAULT_STREAM_PORT,
                         help=f'Порт стрима (по умолчанию: {DEFAULT_STREAM_PORT})')
stream_group.add_argument('--stream-fps', type=int, default=DEFAULT_STREAM_FPS,
                         help=f'Частота кадров стрима (по умолчанию: {DEFAULT_STREAM_FPS})')
stream_group.add_argument('--stream-quality', type=int, default=DEFAULT_STREAM_QUALITY,
                         help=f'Качество JPEG стрима 1-100 (по умолчанию: {DEFAULT_STREAM_QUALITY})')
stream_group.add_argument('--stream-analysis', action='store_true', default=DEFAULT_STREAM_ANALYSIS,
                         help='Включить анализ шахматной доски в стриме (замедляет)')
stream_group.add_argument('--no-analysis', action='store_false', dest='stream_analysis',
                         help='Отключить анализ в стриме (рекомендуется)')
stream_group.add_argument('--low-latency', action='store_true', default=DEFAULT_STREAM_LOW_LATENCY,
                         help='Режим низкой задержки (по умолчанию: ВКЛЮЧЕН)')

# Группа параметров съемки
capture_group = parser.add_argument_group('Параметры съемки')
capture_group.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                          help=f'Задержка перед снимком в секундах (по умолчанию: {DEFAULT_DELAY})')
capture_group.add_argument('--count', type=int, default=DEFAULT_COUNT,
                          help=f'Количество изображений (по умолчанию: {DEFAULT_COUNT})')
capture_group.add_argument('--output-dir', type=str, default=DEFAULT_OUTPUT_DIR,
                          help=f'Выходная директория (по умолчанию: "{DEFAULT_OUTPUT_DIR}")')
capture_group.add_argument('--jpeg-quality', type=int, default=DEFAULT_JPEG_QUALITY,
                          help=f'Качество JPEG снимков 1-100 (по умолчанию: {DEFAULT_JPEG_QUALITY})')

# Группа параметров контроля углов (только для съемки)
angle_group = parser.add_argument_group('Контроль углов наклона (только при съемке)')
angle_group.add_argument('--max-angle', type=float, default=MAX_ACCEPTABLE_ANGLE,
                        help=f'Максимальный допустимый угол наклона (градусы) (по умолчанию: {MAX_ACCEPTABLE_ANGLE})')
angle_group.add_argument('--warn-angle', type=float, default=WARNING_ANGLE,
                        help=f'Угол для предупреждения (градусы) (по умолчанию: {WARNING_ANGLE})')
angle_group.add_argument('--force-capture', action='store_true',
                        help='Делать снимки даже при большом угле наклона')

# Группа параметров отображения
display_group = parser.add_argument_group('Параметры отображения')
display_group.add_argument('--preview', action='store_true', default=DEFAULT_PREVIEW_ENABLED,
                          help='Показывать окно предпросмотра')

# Группа параметров отладки
debug_group = parser.add_argument_group('Параметры отладки')
debug_group.add_argument('--debug', action='store_true', help='Включить вывод отладки')
debug_group.add_argument('--test-stream', action='store_true', help='Тест только стрима')
debug_group.add_argument('--list-cameras', action='store_true', help='Показать список доступных камер')


# Группа параметров экспозиции и фокусировки
expofocus_group = parser.add_argument_group('Параметры экспозиции и фокусировки')
expofocus_group.add_argument('--exposure-time', type=int, default=DEFAULT_EXPOSURE_TIME,
                           help=f'Выдержка в микросекундах (по умолчанию: {DEFAULT_EXPOSURE_TIME})')
expofocus_group.add_argument('--analogue-gain', type=float, default=DEFAULT_ANALOGUE_GAIN,
                           help=f'Аналоговое усиление (по умолчанию: {DEFAULT_ANALOGUE_GAIN})')
expofocus_group.add_argument('--ae-enable', action='store_true', default=DEFAULT_AE_ENABLE,
                           help=f'Включить автоэкспозицию (по умолчанию: {"ВЫКЛ" if not DEFAULT_AE_ENABLE else "ВКЛ"})')
expofocus_group.add_argument('--no-ae', action='store_false', dest='ae_enable',
                           help='Выключить автоэкспозицию')
expofocus_group.add_argument('--af-enable', action='store_true', default=DEFAULT_AF_ENABLE,
                           help=f'Включить автофокус (по умолчанию: {"ВЫКЛ" if not DEFAULT_AF_ENABLE else "ВКЛ"})')
expofocus_group.add_argument('--no-af', action='store_false', dest='af_enable',
                           help='Выключить автофокус')
expofocus_group.add_argument('--lens-position', type=float, default=DEFAULT_LENS_POSITION,
                           help=f'Позиция линзы (по умолчанию: {DEFAULT_LENS_POSITION})')


# ===========================================
# КЛАСС ДЛЯ СТРИМИНГА С НИЗКОЙ ЗАДЕРЖКОЙ
# ===========================================

class LowLatencyStreamHandler(SimpleHTTPRequestHandler):
    """Обработчик стрима с минимальной задержкой"""
    
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
            print(f"🔌 Отключение от стрима: {e}")
        except Exception as e:
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
        
        status = {{
            "camera": self.server.camera_name,
            "stream_resolution": f"{self.server.stream_width}x{self.server.stream_height}",
            "stream_fps": self.server.stream_fps,
            "stream_quality": self.server.stream_quality,
            "stream_analysis": self.server.stream_analysis,
            "low_latency": self.server.low_latency,
            "timestamp": time.time()
        }}
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

class FastStreamingServer(HTTPServer):
    """Сервер стрима с низкой задержкой"""
    
    def __init__(self, server_address, RequestHandlerClass, picam2, camera_info, 
                args, capture_size, save_dir):
        super().__init__(server_address, RequestHandlerClass)
        
        self.picam2 = picam2
        self.camera_name = camera_info['name']
        self.save_dir = save_dir
        
        # Параметры стрима (отдельные от съемки!)
        self.stream_width = args.stream_width
        self.stream_height = args.stream_height
        self.stream_fps = args.stream_fps
        self.stream_quality = args.stream_quality
        self.stream_analysis = args.stream_analysis
        self.low_latency = args.low_latency
        
        # Параметры съемки
        self.capture_width = capture_size[0]
        self.capture_height = capture_size[1]
        self.jpeg_quality = args.jpeg_quality
        self.max_angle = args.max_angle
        self.warn_angle = args.warn_angle
        self.force_capture = args.force_capture
        # Для хранения настроек экспозиции
        self.last_exposure_settings = None        
        
        # Технические параметры
        self.debug_mode = args.debug
        self.latest_frame = None
        self.frame_queue = deque(maxlen=3)  # Буфер на 3 кадра
        self.streaming_active = True
        self.frame_lock = threading.Lock()
        
        # Получаем информацию о сенсоре ДО запуска камеры
        self.sensor_modes = []
        try:
            # Получаем sensor_modes до начала стрима
            self.sensor_modes = self.picam2.sensor_modes
            if self.debug_mode:
                print(f"📊 Доступные режимы сенсора ({len(self.sensor_modes)}):")
                for i, mode in enumerate(self.sensor_modes):
                    size = mode['size']
                    fps = mode.get('fps', 'N/A')
                    bit_depth = mode.get('bit_depth', 'N/A')
                    print(f"  {i}: {size[0]}x{size[1]} @ {fps} FPS, {bit_depth} бит")
        except Exception as e:
            print(f"⚠️  Не удалось получить режимы сенсора: {e}")
        
        # Настраиваем камеру для стрима
        # self.setup_camera_for_stream()
        #self.setup_auto_optimized() 
        
        # Определяем стратегию настройки
        # Настраиваем камеру для стрима
        print(f"\n🔄 Настройка камеры для стрима...")
        print(f"   Камера: {self.camera_name}")
        print(f"   Целевое разрешение: {self.stream_width}x{self.stream_height}")

        # Выбираем стратегию настройки
        if 'imx708' in self.camera_name.lower() and self.stream_width == 1280 and self.stream_height == 720:
            # Для IMX708 1280x720 используем аппаратное масштабирование
            print("   Использую аппаратное масштабирование через lores")
            success = self.setup_imx708_hardware_scaling()
            if not success:
                print("🔄 Аппаратное масштабирование не сработало, пробую простую настройку...")
                success = self.setup_simple_scaling()
                if not success:
                    print("🔄 Простая настройка не сработала, пробую fallback...")
                    self.setup_camera_fallback()
        else:
            # Для других случаев используем простую настройку
            print("   Использую простую настройку")
            success = self.setup_simple_scaling()
            if not success:
                self.setup_camera_fallback()

        # Запуск потока захвата кадров для стрима
        self.start_frame_capture_thread()

    def get_sensor_modes(self):
        """Получение информации о режимах сенсора до запуска камеры"""
        try:
            # Создаем временную конфигурацию для получения информации о сенсоре
            temp_config = self.picam2.create_preview_configuration()
            # Получаем режимы сенсора (это вызовет configure, но камера не запущена)
            modes = self.picam2.sensor_modes
            if self.debug_mode:
                print(f"📊 Доступные режимы сенсора ({len(modes)}):")
                for i, mode in enumerate(modes):
                    size = mode['size']
                    fps = mode.get('fps', 'N/A')
                    bit_depth = mode.get('bit_depth', 'N/A')
                    print(f"  {i}: {size[0]}x{size[1]} @ {fps} FPS, {bit_depth} бит")
            return modes
        except Exception as e:
            print(f"⚠️  Не удалось получить режимы сенсора: {e}")
            return []

    def setup_camera_for_stream(self):
        """Настройка камеры для стрима"""
        
        print(f"🎯 Настройка IMX708 для стрима")
        print(f"   Полное разрешение: 4608x2592")
        print(f"   Стрим: {self.stream_width}x{self.stream_height}")
        
        try:
            # ПРОСТОЙ ВАРИАНТ: используем прямое масштабирование в OpenCV
            # Захватываем полное разрешение, масштабируем в коде
            
            # 1. Настраиваем камеру на полное разрешение
            full_config = self.picam2.create_video_configuration(
                main={"size": (4608, 2592)},
                controls={
                    "FrameRate": self.stream_fps,
                    "ScalerCrop": (0, 0, 4608, 2592)  # Весь сенсор
                }
            )
            
            self.picam2.stop()
            self.picam2.configure(full_config)
            self.picam2.start()
            
            time.sleep(1)  # Даем камере инициализироваться
            
            # 2. Масштабирование будет в потоке захвата кадров
            print(f"✅ Камера настроена на 4608x2592")
            print(f"   Масштабирование до {self.stream_width}x{self.stream_height} в OpenCV")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка настройки: {e}")
            # Пробуем fallback
            try:
                fallback_config = self.picam2.create_video_configuration(
                    main={"size": (self.stream_width, self.stream_height)}
                )
                self.picam2.stop()
                self.picam2.configure(fallback_config)
                self.picam2.start()
                print(f"⚠️  Использую fallback: прямое разрешение {self.stream_width}x{self.stream_height}")
                return True
            except:
                return False
    
    def start_frame_capture_thread(self):
        """Запуск потока захвата с фиксированной обработкой формата"""
        def capture_frames():
            frame_count = 0
            
            while self.streaming_active:
                try:
                    # Контроль FPS
                    if frame_count > 0:
                        time.sleep(1.0 / self.stream_fps)
                    
                    # Определяем, откуда захватывать
                    try:
                        if hasattr(self, 'use_lores_stream') and self.use_lores_stream:
                            array = self.picam2.capture_array("lores")
                        else:
                            array = self.picam2.capture_array()
                    except:
                        array = self.picam2.capture_array()
                        if hasattr(self, 'use_lores_stream'):
                            self.use_lores_stream = False
                    
                    if array is None or array.size == 0:
                        time.sleep(0.01)
                        continue
                    
                    # ОТЛАДКА: периодически выводим информацию о формате
                    if self.debug_mode and frame_count % 30 == 0:
                        print(f"📊 Кадр {frame_count}: shape={array.shape}, dtype={array.dtype}")
                    
                    # ЕДИНООБРАЗНАЯ обработка формата
                    if len(array.shape) == 3:
                        # 3D массив
                        if array.shape[2] == 3:
                            # RGB форматы
                            # Проверяем, не является ли это BGR (перевернутым)
                            frame = array.copy()
                            # Если камера возвращает RGB, конвертируем в BGR для OpenCV
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        elif array.shape[2] == 4:
                            # RGBA или RAW с 4 каналами
                            # Берем только RGB и конвертируем
                            frame = array[:, :, :3]
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        else:
                            # Неизвестный формат
                            print(f"⚠️  Неизвестный 3D формат: {array.shape[2]} каналов")
                            continue
                    elif len(array.shape) == 2:
                        # 2D массив - монохромный
                        frame = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
                    else:
                        # Неизвестная размерность
                        print(f"⚠️  Неизвестная размерность: {len(array.shape)}")
                        continue
                    
                    # Масштабируем только если нужно и НЕ используем lores
                    if not hasattr(self, 'use_lores_stream') or not self.use_lores_stream:
                        if (frame.shape[1], frame.shape[0]) != (self.stream_width, self.stream_height):
                            frame = cv2.resize(frame, 
                                            (self.stream_width, self.stream_height),
                                            interpolation=cv2.INTER_AREA)
                    
                    # Сохраняем кадр
                    with self.frame_lock:
                        self.latest_frame = frame
                    
                    frame_count += 1
                        
                except Exception as e:
                    if self.debug_mode and frame_count % 10 == 0:
                        print(f"⚠️  Ошибка захвата: {e}")
                    time.sleep(0.1)
        
        self.capture_thread = threading.Thread(target=capture_frames, daemon=True)
        self.capture_thread.start()
        print("✅ Поток захвата кадров запущен (фиксированный формат)")

    def switch_to_full_resolution(self):
        """Переключение на полное разрешение для съемки"""
        try:
            if self.streaming_active:
                self.streaming_active = False
                time.sleep(0.2)
            
            print(f"🔄 Переключение на полное разрешение: {self.capture_width}x{self.capture_height}")
            
            # Фиксируем экспозицию перед остановкой камеры
            exposure_settings = self.lock_exposure_before_capture()
            
            # Сохраняем текущие настройки цвета для восстановления
            try:
                metadata = self.picam2.capture_metadata()
                self.last_color_settings = {
                    "AwbEnable": metadata.get("AwbEnable", True),
                    "AwbMode": metadata.get("AwbMode", 0),
                    "ColourGains": metadata.get("ColourGains", (1.0, 1.0))
                }
            except:
                self.last_color_settings = {"AwbEnable": True, "AwbMode": 0}
            
            # Останавливаем камеру
            try:
                self.picam2.stop()
            except:
                pass
            
            # Базовые настройки для съемки с ЯВНЫМ цветным форматом
            base_controls = {
                "FrameRate": 5,
                "AwbEnable": DEFAULT_AWB_ENABLE,
                "AeEnable": DEFAULT_AE_ENABLE,
                "NoiseReductionMode": 2,  # Высокое качество для фото
            }
            
            # Добавляем фиксированные настройки экспозиции
            base_controls.update(exposure_settings)
            
            # Настройки фокуса
            if "imx708" in self.camera_name.lower():
                base_controls["LensPosition"] = DEFAULT_LENS_POSITION
            
            if self.debug_mode:
                print(f"📊 Используем контролы для фото: {base_controls}")
            
            # Создаем конфигурацию для съемки с ЯВНЫМ форматом
            capture_config = self.picam2.create_still_configuration(
                main={
                    "size": (self.capture_width, self.capture_height),
                    "format": "RGB888"  # Явно указываем цветной формат
                },
                controls=base_controls,
                buffer_count=4
            )
            
            # Конфигурируем и запускаем
            self.picam2.configure(capture_config)
            self.picam2.start()
            
            # Даем камере время на стабилизацию
            time.sleep(1.0)
            
            print(f"✅ Камера настроена на {self.capture_width}x{self.capture_height} для фото")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка переключения на полное разрешение: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            return False
            
    def switch_to_stream_resolution(self):
        """Переключение камеры обратно на разрешение стрима с сохранением формата"""
        try:
            print(f"🔄 Возврат к стриму: {self.stream_width}x{self.stream_height}")
            
            # Получаем текущие настройки фото
            current_exposure = {}
            try:
                metadata = self.picam2.capture_metadata()
                if "ExposureTime" in metadata:
                    current_exposure["ExposureTime"] = metadata["ExposureTime"]
                if "AnalogueGain" in metadata:
                    current_exposure["AnalogueGain"] = metadata["AnalogueGain"]
            except:
                pass
            
            # Останавливаем камеру
            try:
                self.picam2.stop()
            except:
                pass
            
            # Настройки для стрима с ЯВНЫМ форматом
            stream_controls = {
                "FrameRate": self.stream_fps,
                "NoiseReductionMode": 1,  # Быстрый для стрима
                "AwbEnable": True,  # Автобаланс белого
                "AeEnable": True,   # Автоэкспозиция
            }
            
            # Если есть настройки с фото, используем как стартовые
            if current_exposure:
                stream_controls.update(current_exposure)
            
            # Восстанавливаем сохраненные настройки цвета
            if hasattr(self, 'last_color_settings'):
                stream_controls.update(self.last_color_settings)
            
            print(f"📊 Восстанавливаю стрим с контролами: {stream_controls}")
            
            # Используем ту же стратегию настройки, что и при старте
            if 'imx708' in self.camera_name.lower() and self.stream_width == 1280 and self.stream_height == 720:
                # Для IMX708 1280x720 используем аппаратное масштабирование
                print("   Восстанавливаю аппаратное масштабирование")
                if hasattr(self, 'use_lores_stream'):
                    # Пробуем восстановить lores
                    success = self.setup_imx708_hardware_scaling()
                    if not success:
                        print("🔄 Аппаратное не сработало, использую простую настройку")
                        success = self.setup_simple_scaling()
                else:
                    success = self.setup_simple_scaling()
            else:
                # Простая настройка
                success = self.setup_simple_scaling()
            
            if not success:
                print("🔄 Не удалось восстановить, использую fallback")
                # Fallback конфигурация
                fallback_config = self.picam2.create_video_configuration(
                    main={
                        "size": (self.stream_width, self.stream_height),
                        "format": "RGB888"
                    },
                    controls=stream_controls
                )
                self.picam2.configure(fallback_config)
                self.picam2.start()
            
            # Очищаем буфер кадров
            with self.frame_lock:
                self.latest_frame = None
                self.frame_queue.clear()
            
            # Быстрый старт стрима
            self.streaming_active = True
            
            # Перезапускаем поток захвата
            if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=0.5)
            self.start_frame_capture_thread()
            
            # Даем камере время на стабилизацию
            time.sleep(0.5)
            
            print(f"✅ Стрим восстановлен")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка восстановления стрима: {e}")
            # Пытаемся восстановить
            try:
                self.picam2.start()
                self.streaming_active = True
            except:
                pass
            return False

    def get_latest_frame(self):
        """Получение самого свежего кадра"""
        with self.frame_lock:
            if self.frame_queue:
                return self.frame_queue[-1]  # Просто возвращаем кадр
            return self.latest_frame
        
    def capture_high_res_frame(self):
        """Захват кадра в высоком разрешении для сохранения"""
        try:
            # Останавливаем стрим на время захвата высокого разрешения
            self.streaming_active = False
            time.sleep(0.1)  # Даем время остановиться
            
            # Конфигурация для съемки
            if self.capture_width > self.stream_width or self.capture_height > self.stream_height:
                # Нужно переключиться на высокое разрешение
                capture_config = self.picam2.create_still_configuration(
                    main={"size": (self.capture_width, self.capture_height)}
                )
                
                self.picam2.stop()
                self.picam2.configure(capture_config)
                self.picam2.start()
                time.sleep(0.5)  # Даем камере время на переключение
            
            # Захват кадра
            array = self.picam2.capture_array()
            
            if len(array.shape) == 3 and array.shape[2] == 3:
                # Камера возвращает RGB, но для OpenCV конвертируем в BGR
                frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            else:
                frame = array
            
            # Возвращаемся к стриму
            if self.capture_width > self.stream_width or self.capture_height > self.stream_height:
                stream_config = self.picam2.create_video_configuration(
                    main={"size": (self.stream_width, self.stream_height)},
                    controls={"FrameRate": self.stream_fps}
                )
                self.picam2.stop()
                self.picam2.configure(stream_config)
                self.picam2.start()
            
            self.streaming_active = True
            return frame
            
        except Exception as e:
            print(f"❌ Ошибка захвата высокого разрешения: {e}")
            self.streaming_active = True
            return None

    def restart_capture_thread(self):
        """Безопасная перезагрузка потока захвата кадров"""
        self.streaming_active = False
        time.sleep(0.2)
        
        # Ждем завершения потока
        if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        
        # Запускаем заново
        self.streaming_active = True
        self.start_frame_capture_thread()

    def capture_high_res_photo(self):
        """Захват и сохранение фото в высоком разрешении"""
        try:
            print(f"📸 Захват фото {self.capture_width}x{self.capture_height}...")
            
            # Сохраняем текущие настройки стрима
            self.save_stream_state()
            
            # Переключаемся на полное разрешение
            if not self.switch_to_full_resolution():
                print("❌ Не удалось переключить камеру на полное разрешение")
                self.restore_stream_state()
                return None
            
            # Захват фото в полном разрешении
            print("📷 Захват кадра...")
            
            # Несколько попыток для стабилизации
            for attempt in range(3):
                try:
                    array = self.picam2.capture_array()
                    if array is not None and array.size > 0:
                        break
                    time.sleep(0.1)
                except:
                    time.sleep(0.1)
            else:
                print("❌ Не удалось захватить кадр")
                self.restore_stream_state()
                return None
            
            print("_________________________________________________________________________________")
            # Анализируем формат полученного кадра
            if len(array.shape) == 3:
                if array.shape[2] == 3:
                    # RGB формат
                    frame_rgb = array
                    #frame_rgb = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)  не работает
                    print(f"📊 Формат фото: RGB, размер: {array.shape[1]}x{array.shape[0]}")
                elif array.shape[2] == 4:
                    # RGBA или RAW - конвертируем
                    print(f"⚠️  RAW формат: {array.shape[2]} канала, конвертирую...")
                    frame_rgb = array[:, :, :3]  # Берем первые 3 канала
                else:
                    print(f"⚠️  Неизвестный формат: {array.shape[2]} каналов")
                    frame_rgb = array
            else:
                # Монохромный
                print("⚠️  Монохромный формат, конвертирую в цветной...")
                frame_rgb = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)
            

            # Проверяем размер кадра
            height, width = frame_rgb.shape[:2]
            print(f"📐 Фактический размер кадра: {width}x{height}")
            
            # Проверяем экспозицию
            if len(frame_rgb.shape) == 3:
                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                avg_brightness = np.mean(gray)
                print(f"📊 Средняя яркость: {avg_brightness:.0f}/255")
            
            # Генерируем имя файла
            timestamp = int(time.time())
            existing_files = [f for f in os.listdir(self.save_dir) 
                            if f.startswith('chessboard_') and f.endswith('.jpg')]
            
            max_number = 0
            for file in existing_files:
                try:
                    parts = file.split('_')
                    if len(parts) >= 2 and parts[1].isdigit():
                        max_number = max(max_number, int(parts[1]))
                except:
                    continue
            
            next_number = max_number + 1
            filename = f"chessboard_{next_number:03d}_{timestamp}.jpg"
            filepath = os.path.join(self.save_dir, filename)
            
            # Сохраняем с высоким качеством
            # OpenCV ожидает BGR, но у нас RGB, конвертируем
            #frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            #cv2.imwrite(filepath, frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
            
            #frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            cv2.imwrite(filepath, frame_rgb, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])

            # Восстанавливаем стрим
            print("🔄 Возврат к стриму...")
            if not self.restore_stream_state():
                print("⚠️  Не удалось полностью восстановить стрим")
            
            # Проверяем файл
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath) / 1024
                print(f"✅ Сохранено: {filename}")
                print(f"   Размер файла: {file_size:.1f} КБ")
                print(f"   Размер изображения: {width}x{height}")
                return filename
            else:
                print(f"❌ Ошибка сохранения файла")
                return None
            
        except Exception as e:
            print(f"❌ Ошибка захвата фото: {e}")
            # Пытаемся вернуться к стриму в любом случае
            try:
                self.restore_stream_state()
            except:
                pass
            return None

    def save_stream_state(self):
        """Сохраняем состояние стрима перед переключением"""
        self.saved_stream_state = {
            'streaming_active': self.streaming_active,
            'use_lores_stream': getattr(self, 'use_lores_stream', False),
            'camera_name': self.camera_name,
            'stream_width': self.stream_width,
            'stream_height': self.stream_height,
            'stream_fps': self.stream_fps
        }
        print("💾 Сохранено состояние стрима")

    def restore_stream_state(self):
        """Восстанавливаем состояние стрима"""
        print("🔄 Восстанавливаю состояние стрима...")
        
        if not hasattr(self, 'saved_stream_state'):
            print("⚠️  Нет сохраненного состояния, использую стандартное восстановление")
            return self.switch_to_stream_resolution()
        
        state = self.saved_stream_state
        
        try:
            # Останавливаем стрим
            self.streaming_active = False
            time.sleep(0.1)
            
            # Останавливаем камеру
            try:
                self.picam2.stop()
            except:
                pass
            
            # Восстанавливаем настройки
            if state.get('use_lores_stream', False) and 'imx708' in state['camera_name'].lower():
                print("   Восстанавливаю аппаратное масштабирование")
                success = self.setup_imx708_hardware_scaling()
            else:
                print("   Восстанавливаю простую настройку")
                success = self.setup_simple_scaling()
            
            if not success:
                print("🔄 Не удалось, использую fallback")
                self.setup_camera_fallback()
            
            # Восстанавливаем поток
            self.streaming_active = True
            if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=0.5)
            self.start_frame_capture_thread()
            
            time.sleep(0.3)
            print("✅ Состояние стрима восстановлено")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка восстановления: {e}")
            return False

    def analyze_frame(self, frame):
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
    
    def analyze_chessboard_angle(self, frame):
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

    def lock_exposure_before_capture(self):
        """Фиксация экспозиции перед съемкой"""
        try:
            print("🔒 Фиксация экспозиции...")
            
            # Даем камере время стабилизироваться
            time.sleep(0.5)
            
            # Делаем пробный захват для обновления AE
            try:
                self.picam2.capture_array()
                time.sleep(0.2)
            except:
                pass
            
            # Получаем метаданные
            metadata = self.picam2.capture_metadata()
            
            if self.debug_mode:
                print(f"📊 Метаданные камеры: {metadata}")
            
            exposure_settings = {"AeEnable": False}
            
            # Получаем текущие параметры экспозиции
            if "ExposureTime" in metadata:
                exposure_time = metadata["ExposureTime"]
                exposure_settings["ExposureTime"] = exposure_time
                print(f"   Выдержка: {exposure_time/1000:.0f} мс")
            
            if "AnalogueGain" in metadata:
                analogue_gain = metadata["AnalogueGain"]
                exposure_settings["AnalogueGain"] = analogue_gain
                print(f"   Усиление: {analogue_gain:.2f}")
            
            if "DigitalGain" in metadata and self.debug_mode:
                digital_gain = metadata["DigitalGain"]
                print(f"   Цифровое усиление: {digital_gain:.2f}")
            
            if "AeState" in metadata and self.debug_mode:
                ae_state = metadata["AeState"]
                print(f"   Состояние AE: {ae_state}")
            
            return exposure_settings
            
        except Exception as e:
            print(f"⚠️  Не удалось зафиксировать экспозицию: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            # Возвращаем значения по умолчанию из теста
            return {
                "ExposureTime": 40000,  # 40ms
                "AnalogueGain": 2.0,
                "AeEnable": False
            }

    def setup_camera_with_proper_scaling(self):
        """Настройка камеры с правильным масштабированием 4608x2592 -> стрим-разрешение"""
        
        print(f"🎯 Настройка камеры IMX708:")
        print(f"   Сенсор: 4608x2592 (полный кадр)")
        print(f"   Стрим: {self.stream_width}x{self.stream_height}")
        print(f"   Масштабирование: {4608/self.stream_width:.2f}x")
        
        try:
            # Используем режим сенсора 2 (4608x2592)
            sensor_config = {
                "output_size": (4608, 2592),
                "bit_depth": 10
            }
            
            # Создаем конфигурацию с двумя потоками
            config = self.picam2.create_video_configuration(
                main={"size": (4608, 2592)},  # Полное разрешение для захвата
                lores={"size": (self.stream_width, self.stream_height)},  # Масштабированное для стрима
                sensor=sensor_config,
                controls={
                    "FrameRate": self.stream_fps,
                    "ScalerCrop": (0, 0, 4608, 2592)  # Используем весь сенсор
                }
            )
            
            # Останавливаем и переконфигурируем
            self.picam2.stop()
            self.picam2.configure(config)
            
            # Запускаем камеру
            self.picam2.start()
            
            # Ждем стабилизации
            time.sleep(1.0)
            
            print("✅ Камера настроена с правильным масштабированием")
            
            # Проверяем фактический размер
            array = self.picam2.capture_array()
            print(f"📊 Фактический размер кадра: {array.shape[1]}x{array.shape[0]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка настройки камеры: {e}")
            return False


    def get_optimal_sensor_mode(self):
        """Выбор оптимального режима сенсора"""
        if 'imx708' in self.camera_name.lower():
            if self.stream_width <= 800:
                return {'size': (1536, 864), 'fps': 120}
            elif self.stream_width <= 1920:
                return {'size': (2304, 1296), 'fps': 56}  # ← Оптимально для 1280x720!
            else:
                return {'size': (4608, 2592), 'fps': 14}
        elif 'imx415' in self.camera_name.lower():
            return {'size': (3864, 2192), 'fps': 30}
        else:
            return {'size': (self.stream_width, self.stream_height), 'fps': self.stream_fps}
    
    def setup_auto_optimized(self):
        """Автоматическая оптимизированная настройка"""
        optimal_mode = self.get_optimal_sensor_mode()
        sensor_size = optimal_mode['size']
        max_fps = optimal_mode['fps']
        
        print(f"🤖 Автоматическая оптимизация для {self.camera_name}")
        print(f"   Выбран режим: {sensor_size[0]}x{sensor_size[1]} @ {max_fps} fps")
        print(f"   Целевой стрим: {self.stream_width}x{self.stream_height} @ {self.stream_fps} fps")
        
        try:
            config = self.picam2.create_video_configuration(
                main={"size": (self.stream_width, self.stream_height)},
                # sensor={"output_size": sensor_size},  # УДАЛИТЬ эту строку
                controls={
                    "FrameRate": min(self.stream_fps, max_fps),
                    # "ScalerCrop": (0, 0, sensor_size[0], sensor_size[1]),  # УДАЛИТЬ эту строку!
                    "NoiseReductionMode": 1,
                }
            )
            
            self.picam2.stop()
            self.picam2.configure(config)
            self.picam2.start()
            
            time.sleep(0.5)
            print("✅ Автоматическая оптимизация завершена")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка оптимизации: {e}")
            # Fallback
            return self.setup_camera_fallback()
    
    def setup_camera_fallback(self):
        """Fallback настройка если оптимизация не сработала"""
        print("🔄 Использую fallback настройку...")
        try:
            stream_config = self.picam2.create_video_configuration(
                main={"size": (self.stream_width, self.stream_height)},
                controls={"FrameRate": self.stream_fps}
            )
            self.picam2.stop()
            self.picam2.configure(stream_config)
            self.picam2.start()
            return True
        except:
            return False

    def setup_simple_scaling(self):
        """Простая настройка - позволить системе самой масштабировать"""
        
        print(f"🎯 Простая настройка масштабирования")
        print(f"   Стрим: {self.stream_width}x{self.stream_height}")
        
        try:
            # Просто запрашиваем нужное разрешение
            config = self.picam2.create_video_configuration(
                main={
                    "size": (self.stream_width, self.stream_height),
                    "format": "RGB888"  # Явно указываем цветной формат
                },
                controls={
                    "FrameRate": self.stream_fps,
                    "AwbEnable": True,
                    "AeEnable": True,
                    "NoiseReductionMode": 1,
                }
            )
            
            self.picam2.stop()
            self.picam2.configure(config)
            self.picam2.start()
            
            time.sleep(0.5)
            
            # Проверяем фактический размер
            array = self.picam2.capture_array()
            if array is not None:
                actual_size = (array.shape[1], array.shape[0])
                print(f"✅ Фактический размер кадра: {actual_size[0]}x{actual_size[1]}")
                
                if actual_size != (self.stream_width, self.stream_height):
                    print(f"⚠️  Система выбрала {actual_size[0]}x{actual_size[1]} вместо {self.stream_width}x{self.stream_height}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False          

    def setup_imx708_optimized(self):
        """Оптимизированная настройка для IMX708 с принудительным выбором режима"""
        
        print(f"🎯 Специальная настройка IMX708 для 1280x720")
        print(f"   Принудительно выбираю режим сенсора: 2304x1296")
        
        try:
            # Вариант 1: Использовать lores для аппаратного масштабирования
            config = self.picam2.create_video_configuration(
                main={"size": (2304, 1296)},  # Режим сенсора
                lores={"size": (1280, 720)},   # Масштабированное для стрима
                display="lores",               # Отображаем lores
                encode="lores",                # Кодируем lores
                controls={
                    "FrameRate": self.stream_fps,
                    "NoiseReductionMode": 1,
                }
            )
            
            self.picam2.stop()
            self.picam2.configure(config)
            self.picam2.start()
            
            time.sleep(0.5)
            
            # Тест
            try:
                array = self.picam2.capture_array("lores")
                if array is not None:
                    print(f"✅ Lores поток: {array.shape[1]}x{array.shape[0]}")
                    self.use_lores = True
            except:
                self.use_lores = False
            
            print("✅ IMX708 настроен: 2304x1296 → 1280x720")
            return True
            
        except Exception as e:
            print(f"❌ Lores не сработал: {e}")
            # Пробуем вариант 2
            
            try:
                # Вариант 2: Прямое масштабирование через main
                config = self.picam2.create_video_configuration(
                    main={"size": (1280, 720)},
                    sensor={"output_size": (2304, 1296)},  # Принудительно режим сенсора
                    controls={
                        "FrameRate": self.stream_fps,
                        "NoiseReductionMode": 1,
                    }
                )
                
                self.picam2.stop()
                self.picam2.configure(config)
                self.picam2.start()
                
                time.sleep(0.5)
                
                print("✅ IMX708 настроен через sensor output_size")
                return True
                
            except Exception as e2:
                print(f"❌ Sensor output_size не сработал: {e2}")
                
                # Вариант 3: Fallback - простая настройка
                return self.setup_simple_scaling()


    def setup_imx708_hardware_scaling(self):
        """Аппаратное масштабирование для IMX708 через lores поток"""
        
        print("🎯 Аппаратное масштабирование IMX708 через lores")
        print(f"   Сенсор: 2304x1296 → Стрим: {self.stream_width}x{self.stream_height}")
        
        try:
            # Останавливаем камеру
            self.picam2.stop()
            time.sleep(0.1)
            
            # Создаем конфигурацию с двумя потоками:
            # - main: полное разрешение сенсора (2304x1296)
            # - lores: масштабированное для стрима (1280x720)
            config = self.picam2.create_video_configuration(
                main={
                    "size": (2304, 1296),  # Режим сенсора IMX708
                    "format": "RGB888"     # Цветной формат
                },
                lores={
                    "size": (self.stream_width, self.stream_height),  # Масштабированный стрим
                    "format": "RGB888"                                # Цветной формат
                },
                display="lores",    # Отображаем lores поток
                encode="lores",     # Кодируем lores поток
                controls={
                    "FrameRate": min(self.stream_fps, 30),  # Ограничиваем FPS
                    "AwbEnable": True,     # Баланс белого
                    "AeEnable": True,      # Автоэкспозиция
                    "NoiseReductionMode": 1,  # Быстрый шумодав
                },
                queue=False,        # Отключаем буферизацию для меньшей задержки
                buffer_count=2      # Минимальное количество буферов
            )
            
            # Конфигурируем камеру
            self.picam2.configure(config)
            
            # Устанавливаем флаг использования lores
            self.use_lores_stream = True
            
            # Запускаем камеру
            self.picam2.start()
            
            # Ждем инициализации
            time.sleep(1.0)
            
            # Проверяем, что lores поток работает
            try:
                test_frame = self.picam2.capture_array("lores")
                if test_frame is not None:
                    print(f"✅ Lores поток работает: {test_frame.shape[1]}x{test_frame.shape[0]}")
                    print(f"   Формат: {test_frame.shape[2]} канала(ов)")
                    return True
            except Exception as e:
                print(f"⚠️  Не удалось захватить lores: {e}")
                self.use_lores_stream = False
            
            print("✅ Аппаратное масштабирование настроено")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка аппаратного масштабирования: {e}")
            self.use_lores_stream = False
            return False
# ===========================================
# ОСНОВНЫЕ ФУНКЦИИ
# ===========================================

def start_stream_server(args, picam2, camera_info, capture_size, save_dir):
    """Запуск стрим-сервера"""
    server_address = ('', args.stream_port)
    
    httpd = FastStreamingServer(
        server_address, 
        LowLatencyStreamHandler, 
        picam2, 
        camera_info,
        args,  # передаем args целиком
        capture_size,
        save_dir
    )
    
    print(f"\n{'='*70}")
    print(f"🚀 СТРИМ-СЕРВЕР ЗАПУЩЕН")
    print(f"{'='*70}")
    print(f"📷 Камера: {camera_info['name']}")
    print(f"🎬 Стрим: {args.stream_width}x{args.stream_height} @ {args.stream_fps} FPS")
    print(f"📸 Съемка: {capture_size[0]}x{capture_size[1]}")
    print(f"🔍 Анализ в стриме: {'ВКЛ' if args.stream_analysis else 'ВЫКЛ'}")
    print(f"⚡ Режим низкой задержки: {'ВКЛ' if args.low_latency else 'ВЫКЛ'}")
    print(f"{'='*70}")
    print(f"📡 Локальный URL: http://localhost:{args.stream_port}")
    print(f"🌐 Сетевой URL: http://{socket.gethostname()}.local:{args.stream_port}")
    print(f"{'='*70}")
    print("💡 Для минимальной задержки используйте:")
    print("   --no-analysis --low-latency --stream-fps 30")
    print("   --stream-width 640 --stream-height 480")
    
    return httpd

def run_server(httpd):
    """Запуск сервера в отдельном потоке"""
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Остановка стрим-сервера...")
    finally:
        httpd.streaming_active = False
        httpd.server_close()
        print("✅ Стрим-сервер остановлен")

def test_stream_latency(args):
    """Тестирование задержки стрима"""
    print("⏱️ Тестирование задержки стрима...")
    
    try:
        picam2 = Picamera2(0)
        
        # Тестируем разные разрешения
        test_resolutions = [
            (640, 480),
            (1280, 720),
            (1920, 1080)
        ]
        
        for width, height in test_resolutions:
            print(f"\n📐 Тест {width}x{height}:")
            
            config = picam2.create_video_configuration(
                main={"size": (width, height)},
                controls={"FrameRate": args.stream_fps}
            )
            
            picam2.stop()
            picam2.configure(config)
            picam2.start()
            time.sleep(1)  # Даем камере время
            
            # Измеряем задержку
            test_frames = 10
            latencies = []
            
            for i in range(test_frames):
                start_time = time.time()
                array = picam2.capture_array()
                capture_time = time.time() - start_time
                
                # Кодирование
                if len(array.shape) == 3 and array.shape[2] == 3:
                    frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                else:
                    frame = array
                
                encode_start = time.time()
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, args.stream_quality])
                encode_time = time.time() - encode_start
                
                total_latency = capture_time + encode_time
                latencies.append(total_latency * 1000)  # в мс
                
                time.sleep(1.0 / args.stream_fps)
            
            avg_latency = sum(latencies) / len(latencies)
            print(f"  📊 Средняя задержка: {avg_latency:.0f} мс")
            print(f"  📈 Min: {min(latencies):.0f} мс, Max: {max(latencies):.0f} мс")
        
        picam2.stop()
        print(f"\n✅ Тест завершен")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

def capture_single_photo(httpd):
    """Захват одного фото через сервер"""
    if httpd is None:
        print("❌ Стрим-сервер не запущен!")
        return None
    
    print(f"📸 Захват фото...")
    
    # Временно приостанавливаем стрим для всех клиентов
    httpd.streaming_active = False
    time.sleep(0.1)  # Даем завершить текущие отправки
    
    try:
        filename = httpd.capture_high_res_photo()
        return filename
    finally:
        # Всегда восстанавливаем стрим
        httpd.streaming_active = True
        # Перезапускаем поток захвата
        httpd.restart_capture_thread()

def select_camera_by_type(camera_type, debug=False):
    """Выбор камеры по типу"""
    selected_picam2 = None
    selected_index = -1
    
    try:
        # Пробуем разные индексы камер
        for i in range(3):
            temp_picam2 = None
            try:
                temp_picam2 = Picamera2(i)
                
                # Получаем информацию о камере
                camera_info = temp_picam2.camera_properties
                camera_name = camera_info.get('Model', '')
                
                if debug:
                    print(f"🔍 Камера #{i}: {camera_name}")
                
                # Проверяем соответствие типу
                if camera_type == 'imx415' and 'imx415' in camera_name.lower():
                    print(f"✅ Найдена IMX415 (камера #{i})")
                    selected_picam2 = temp_picam2
                    selected_index = i
                    break
                elif camera_type == 'imx708' and 'imx708' in camera_name.lower():
                    print(f"✅ Найдена IMX708 (камера #{i})")
                    selected_picam2 = temp_picam2
                    selected_index = i
                    break
                elif camera_type == 'ov5647' and 'ov5647' in camera_name.lower():
                    print(f"✅ Найдена OV5647 (камера #{i})")
                    selected_picam2 = temp_picam2
                    selected_index = i
                    break
                else:
                    # Закрываем временную камеру
                    temp_picam2.close()
                    
            except Exception as e:
                if debug:
                    print(f"⚠️  Камера #{i}: {e}")
                if temp_picam2:
                    try:
                        temp_picam2.close()
                    except:
                        pass
                continue
        
        # Если не нашли по имени, используем первую доступную
        if selected_picam2 is None:
            print("⚠️  Камера по типу не найдена, использую первую доступную")
            try:
                selected_picam2 = Picamera2(0)
                selected_index = 0
            except Exception as e:
                print(f"❌ Нет доступных камер: {e}")
                return None, -1
        
        return selected_picam2, selected_index
        
    except Exception as e:
        print(f"❌ Ошибка выбора камеры: {e}")
        return None, -1



def main():
    """Основная функция"""
    args = parser.parse_args()
    
    # Тестовые режимы
    if args.test_stream:
        test_stream_latency(args)
        return
    
    if args.list_cameras:
        # Простая проверка камер
        for i in range(4):
            try:
                picam2 = Picamera2(i)
                camera_info = picam2.camera_properties
                camera_name = camera_info.get('Model', 'Unknown')
                print(f"✅ Камера {i}: {camera_name}")
                picam2.close()
            except:
                print(f"❌ Камера {i}: Недоступна")
        return
    
    # Получаем информацию о камере
    if args.camera not in CAMERA_PROFILES:
        print(f"❌ Неизвестная камера: {args.camera}")
        return
    
    camera_info = CAMERA_PROFILES[args.camera]
    
    # Определяем разрешение съемки
    if args.resolution == 'full':
        capture_size = camera_info['full_resolution']
        print(f"📸 Режим съемки: ПОЛНОЕ РАЗРЕШЕНИЕ ({capture_size[0]}x{capture_size[1]})")
    else:
        # Для стримового разрешения съемки используем стримовые параметры
        capture_size = (args.stream_width, args.stream_height)
        print(f"📸 Режим съемки: СТРИМОВОЕ РАЗРЕШЕНИЕ ({capture_size[0]}x{capture_size[1]})")
    
    # Вывод информации
    print("=" * 70)
    print("📷 КАЛИБРОВКА КАМЕРЫ С ОТДЕЛЬНЫМИ НАСТРОЙКАМИ СТРИМА")
    print("=" * 70)
    
    print(f"\n🎯 КАМЕРА: {camera_info['name']}")
    print(f"   📸 Съемка: {capture_size[0]}x{capture_size[1]} ({args.resolution} режим)")
    print(f"   🎬 Стрим: {args.stream_width}x{args.stream_height} @ {args.stream_fps} FPS")
    print(f"   🔍 Анализ в стриме: {'ВКЛ' if args.stream_analysis else 'ВЫКЛ'}")
    print(f"   ⚡ Низкая задержка: {'ВКЛ' if args.low_latency else 'ВЫКЛ'}")
    
    print(f"\n🎯 ПАРАМЕТРЫ:")
    print(f"   Количество снимков: {args.count}")
    print(f"   Качество снимков: {args.jpeg_quality}/100")
    print(f"   Качество стрима: {args.stream_quality}/100")
    print(f"   Контроль углов: {args.max_angle}° макс.")
    
    print(f"\n🎯 СТРИМ: {'✅ ВКЛЮЧЕН' if args.stream else '❌ ВЫКЛЮЧЕН'}")
    if args.stream:
        print(f"   Порт: {args.stream_port}")
        print(f"   Ожидаемая задержка: {'<100 мс' if args.low_latency else '>500 мс'}")
    
    print("=" * 70)
    
    # ВЫЗОВ ФУНКЦИИ ВЫБОРА КАМЕРЫ
    print("\n🔍 Поиск камеры...")
    picam2, camera_index = select_camera_by_type(args.camera, args.debug)
    
    if picam2 is None:
        print(f"❌ Не удалось инициализировать камеру {args.camera}")
        return
    
    print(f"✅ Используется камера #{camera_index}: {camera_info['name']}")
    
    # Создаем директорию для сохранения
    save_dir = args.output_dir
    os.makedirs(save_dir, exist_ok=True)
    
    # Запускаем сервер если нужно
    httpd = None
    if args.stream:
        print(f"\n🔄 Запуск стрима...")
        
        # Создаем сервер
        httpd = start_stream_server(args, picam2, camera_info, capture_size, save_dir)
        
        # Запускаем сервер в отдельном потоке
        server_thread = threading.Thread(
            target=run_server,
            args=(httpd,),
            daemon=True
        )
        server_thread.start()
        
        # Ждем запуска сервера
        time.sleep(2)
        print("\n✅ Стрим запущен!")
        print(f"   Откройте браузер: http://localhost:{args.stream_port}")
        print()
    
    # Основной цикл съемки
    try:
        captured_count = 0
        
        for i in range(args.count):
            print(f"{'='*70}")
            print(f"📸 СНИМОК {i+1}/{args.count} (сохранено: {captured_count})")
            if args.resolution == 'full':
                print(f"   ⚠️  ВНИМАНИЕ: Будут сохранены фото в полном разрешении {capture_size[0]}x{capture_size[1]}")
            print(f"{'='*70}")
            
            if args.stream:
                print(f"📱 Стрим: http://localhost:{args.stream_port}")
                print("   Откройте в браузере для прицеливания")
                print("   После кадрирования вернитесь в терминал")
            
            print("\nКоманды:")
            print("  [Enter] - сделать снимок")
            print("  [s]     - пропустить")
            print("  [q]     - завершить")
            print("  [t]     - тестовый снимок (стрим)")
            
            choice = input("\nВыбор [Enter/s/q/t]: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 's':
                continue
            elif choice == 't':
                # Тестовый снимок в разрешении стрима
                if args.stream:
                    print("📸 Делаем тестовый снимок...")
                    filename = capture_single_photo(httpd)
                    if filename:
                        print(f"✅ Тестовый снимок: {filename}")
                else:
                    print("❌ Стрим не включен. Используйте --stream")
                continue
            
            # Основной снимок
            print(f"\n⏱️  Съемка через {args.delay} сек...")
            for sec in range(int(args.delay), 0, -1):
                print(f"  {sec}...")
                time.sleep(1)
            
            print("📸 Съемка!")
            
            # Захват и сохранение фото
            if args.stream:
                filename = capture_single_photo(httpd)
                if filename:
                    captured_count += 1
                    print(f"✅ Снимок #{captured_count} сохранен: {filename}")
                else:
                    print("❌ Не удалось сохранить снимок")
            else:
                print("⚠️  Стрим не активен, используйте --stream")
                
        print(f"\n✅ Съемка завершена! Сохранено снимков: {captured_count}/{args.count}")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Прервано")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        if httpd:
            httpd.streaming_active = False
            httpd.server_close()
            print("\n✅ Стрим-сервер остановлен")

# ===========================================
# ЗАПУСК
# ===========================================

if __name__ == "__main__":
    main()