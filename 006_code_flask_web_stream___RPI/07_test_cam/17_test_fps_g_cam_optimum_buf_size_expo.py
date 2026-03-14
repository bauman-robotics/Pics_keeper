#!/usr/bin/env python3
"""
Скрипт для тестового захвата видео в разных разрешениях
С поддержкой различных оптимизаций для сравнения
"""

import cv2
import time
import os
import subprocess
import sys
import threading
import numpy as np
from collections import deque
from datetime import datetime
from queue import Queue

# ============================================================
# ПАРАМЕТРЫ ПО УМОЛЧАНИЮ (можно изменить перед запуском)
# ============================================================

# Основные параметры
DEVICE_ID = 16              # ID видеоустройства (/dev/video{DEVICE_ID})
OUTPUT_DIR = "camera_test_videos"  # директория для сохранения видео
LOGS_DIR = "logs"           # директория для логов

# ============================================================
# МАКРОС ДЛЯ АВТОМАТИЧЕСКОГО РЕЖИМА
# ============================================================
RUN_DEFAULT = True  # Автоматический режим

# ============================================================
# МАКРОСЫ ДЛЯ ВКЛЮЧЕНИЯ ОПТИМИЗАЦИЙ (для сравнения)
# ============================================================

# Базовый режим (как сейчас)
USE_BASELINE = False  # Если True - остальные оптимизации игнорируются

# Оптимизация 1: Кольцевой буфер (вместо списка)
USE_RING_BUFFER = True

# Оптимизация 2: Многопоточность (Producer-Consumer)
USE_THREADING = True

# Оптимизация 3: Pre-allocated numpy массив
USE_NUMPY_PREALLOC = True # False #True

# Комбинированный режим (все оптимизации вместе)
USE_ALL_OPTIMIZATIONS = True #  False  # Если True - включает все оптимизации выше

# ============================================================
# ПАРАМЕТРЫ РЕЖИМА DEFAULT
# ============================================================
DEFAULT_BACKEND = 'MJPEG'    # 'MJPEG' или 'YUYV'
DEFAULT_WIDTH = 1920          # ширина кадра
DEFAULT_HEIGHT = 1200         # высота кадра
DEFAULT_FPS = 90             # целевой FPS
DEFAULT_DURATION = 5         # длительность записи в секундах

# ============================================================
# Режим экспозиции: 'auto' или 'manual'
EXPOSURE_MODE = 'auto'  # 'auto', 'manual'

# Выдержка в микросекундах (только для manual режима)
# Для 90 fps макс выдержка 11111 мкс (11.1 мс)
EXPOSURE_TIME_US = 100  # 5000 = 5 мс

# ============================================================
# МАКРОСЫ ДЛЯ ОПТИМИЗАЦИИ
# ============================================================

# Режим "только статистика" - без сохранения видео
STATS_ONLY_MODE = False  # False для тестирования оптимизаций в полном режиме

# Параметры буферов
RING_BUFFER_SIZE = 300    # Размер кольцевого буфера (≈ 3-4 секунды при 90 fps)
QUEUE_SIZE = 60           # Размер очереди для многопоточности
NUMPY_BUFFER_SECONDS = 5  # Сколько секунд хранить в pre-allocated буфере

# ============================================================
# Остальные параметры (без изменений)
# ============================================================
TEST_MODES = [
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90, 'name': 'Max resolution @ 90fps'},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60, 'name': 'Max resolution @ 60fps'},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30, 'name': 'Max resolution @ 30fps'},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90, 'name': '720p @ 90fps'},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 60, 'name': '720p @ 60fps'},
    {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90, 'name': 'VGA @ 90fps'},
    {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5, 'name': 'Max YUYV @ 5fps'},
    {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10, 'name': '720p YUYV @ 10fps'},
    {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30, 'name': 'VGA YUYV @ 30fps'},
    {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90, 'name': 'QVGA YUYV @ 90fps'},
]

MJPEG_ONLY_MODES = [
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90},
    {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90},
]

YUYV_ONLY_MODES = [
    {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5},
    {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10},
    {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30},
    {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90},
]

# ============================================================
# КЛАССЫ ДЛЯ РАЗНЫХ ТИПОВ ОПТИМИЗАЦИЙ
# ============================================================

class RingBuffer:
    """Кольцевой буфер для хранения кадров без аллокаций"""
    
    def __init__(self, max_frames, width, height, channels=3):
        self.max_frames = max_frames
        self.width = width
        self.height = height
        self.channels = channels
        
        # Предварительно выделяем память под все кадры
        self.buffer = [None] * max_frames
        self.write_idx = 0
        self.count = 0
        self.lock = threading.Lock()
        
    def add_frame(self, frame):
        """Добавление кадра в буфер (без копирования данных, только ссылка)"""
        with self.lock:
            self.buffer[self.write_idx] = frame
            self.write_idx = (self.write_idx + 1) % self.max_frames
            if self.count < self.max_frames:
                self.count += 1
    
    def get_all_frames(self):
        """Получение всех кадров в правильном порядке"""
        with self.lock:
            if self.count < self.max_frames:
                # Буфер еще не заполнен
                return self.buffer[:self.count]
            else:
                # Буфер заполнен, возвращаем в порядке от старых к новым
                return self.buffer[self.write_idx:] + self.buffer[:self.write_idx]

class NumpyPreallocBuffer:
    """Pre-allocated numpy массив для хранения кадров"""
    
    def __init__(self, max_frames, width, height, channels=3):
        self.max_frames = max_frames
        self.width = width
        self.height = height
        self.channels = channels
        
        # Единый numpy массив под все кадры
        self.buffer = np.zeros((max_frames, height, width, channels), dtype=np.uint8)
        self.write_idx = 0
        self.count = 0
        self.lock = threading.Lock()
        
    def add_frame(self, frame):
        """Добавление кадра с копированием в pre-allocated массив"""
        with self.lock:
            # Копируем данные в существующий массив (без новой аллокации)
            np.copyto(self.buffer[self.write_idx], frame)
            self.write_idx = (self.write_idx + 1) % self.max_frames
            if self.count < self.max_frames:
                self.count += 1
    
    def get_all_frames(self):
        """Получение всех кадров как непрерывный массив"""
        with self.lock:
            if self.count < self.max_frames:
                return self.buffer[:self.count]
            else:
                # Возвращаем в правильном порядке
                return np.concatenate([
                    self.buffer[self.write_idx:],
                    self.buffer[:self.write_idx]
                ])

class ThreadedCapture:
    """Многопоточный захват с очередью"""
    
    def __init__(self, device_id, backend, width, height, target_fps, queue_size=60):
        self.device_id = device_id
        self.backend = backend
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.queue_size = queue_size
        
        self.frame_queue = Queue(maxsize=queue_size)
        self.stop_event = threading.Event()
        self.capture_thread = None
        
        self.frame_count = 0
        self.dropped_frames = 0
        self.bytes_captured = 0
        self.error = None
        self.is_running = False
        
    def start(self):
        """Запуск потока захвата"""
        self.stop_event.clear()
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        # Даем время на инициализацию
        time.sleep(0.5)
        return self.is_running
    
    def stop(self):
        """Остановка захвата"""
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
    
    def _capture_loop(self):
        """Основной цикл захвата в отдельном потоке"""
        cap = None
        try:
            print(f"    [ThreadedCapture] Открытие камеры {self.device_id}...")
            cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)
            
            if not cap.isOpened():
                self.error = "Cannot open camera"
                print(f"    ❌ [ThreadedCapture] {self.error}")
                return
            
            if self.backend.upper() == 'MJPEG':
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            else:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
            
            # Устанавливаем параметры
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            
            # Небольшая задержка для применения параметров
            time.sleep(0.2)
            
            # Проверка установленных параметров
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            
            print(f"    ✅ [ThreadedCapture] Камера открыта: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
            self.is_running = True
            
            while not self.stop_event.is_set():
                ret, frame = cap.read()
                if ret:
                    try:
                        # Пытаемся положить в очередь, не ждем если очередь полна
                        if self.frame_queue.qsize() < self.queue_size:
                            self.frame_queue.put_nowait(frame)
                            self.frame_count += 1
                            self.bytes_captured += frame.nbytes
                        else:
                            self.dropped_frames += 1
                    except Exception as e:
                        # Очередь полна или другая ошибка
                        self.dropped_frames += 1
                else:
                    # Если нет кадра, немного ждем
                    time.sleep(0.001)
                    
        except Exception as e:
            self.error = str(e)
            print(f"    ❌ [ThreadedCapture] Ошибка: {e}")
        finally:
            self.is_running = False
            if cap:
                cap.release()
            print(f"    [ThreadedCapture] Поток завершен")
    
    def get_frame(self, timeout=1.0):
        """Получение кадра из очереди (для основного потока)"""
        try:
            # Используем get с таймаутом
            return self.frame_queue.get(timeout=timeout)
        except Exception:
            # Queue.Empty в Python 3 - это исключение, а не атрибут класса
            return None
    
    def get_stats(self):
        """Получение статистики захвата"""
        return {
            'captured': self.frame_count,
            'dropped': self.dropped_frames,
            'bytes': self.bytes_captured,
            'error': self.error,
            'queue_size': self.frame_queue.qsize()
        }


# ============================================================
# ОСНОВНОЙ КЛАСС ТЕСТЕРА (с поддержкой оптимизаций)
# ============================================================

class Logger:
    # ... (без изменений, как в вашем коде)
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.log_file = None
        self.terminal = sys.stdout
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    def start_logging(self, test_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_test_name = test_name.replace(" ", "_").replace("@", "").replace("|", "-")
        log_filename = f"{self.log_dir}/{timestamp}_{safe_test_name}.log"
        
        self.log_file = open(log_filename, 'w', encoding='utf-8')
        print(f"📝 Лог сохраняется в: {log_filename}")
        return log_filename
    
    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()
        
        if self.log_file:
            self.log_file.write(message)
            self.log_file.flush()
    
    def flush(self):
        self.terminal.flush()
        if self.log_file:
            self.log_file.flush()
    
    def stop_logging(self):
        if self.log_file:
            self.log_file.close()
            self.log_file = None

class VideoCaptureTester:
    def __init__(self, device_id=8, output_dir="test_videos", log_dir="logs"):
        self.device_id = device_id
        self.output_dir = output_dir
        self.log_dir = log_dir
        self.logger = Logger(log_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Создана директория: {output_dir}")
    
    def get_camera_info(self):
        """Получение информации о камере"""
        print("\n" + "="*80)
        print("🔍 ИНФОРМАЦИЯ О КАМЕРЕ")
        print("="*80)
        
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', f'/dev/video{self.device_id}', '--list-formats-ext'],
                capture_output=True,
                text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
    
class VideoCaptureTester:
    def __init__(self, device_id=8, output_dir="test_videos", log_dir="logs"):
        self.device_id = device_id
        self.output_dir = output_dir
        self.log_dir = log_dir
        self.logger = Logger(log_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Создана директория: {output_dir}")
    
    def get_camera_info(self):
        """Получение информации о камере (поддерживаемые форматы)"""
        print("\n" + "="*80)
        print("🔍 ИНФОРМАЦИЯ О КАМЕРЕ")
        print("="*80)
        
        try:
            # Получаем список поддерживаемых форматов
            result = subprocess.run(
                ['v4l2-ctl', '-d', f'/dev/video{self.device_id}', '--list-formats-ext'],
                capture_output=True,
                text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
    
    def get_exposure_info(self):
        """Получение информации о текущих настройках экспозиции"""
        print("\n📸 ТЕКУЩИЕ НАСТРОЙКИ ЭКСПОЗИЦИИ")
        try:
            # Получить режим экспозиции
            result = subprocess.run([
                'v4l2-ctl', '-d', f'/dev/video{self.device_id}',
                '--get-ctrl', 'auto_exposure'
            ], capture_output=True, text=True)
            
            mode_val = result.stdout.strip().split(':')[-1].strip()
            # Расшифровка значения
            modes = {
                '1': 'Manual Mode',
                '2': 'Auto Mode (Constant Iris)',
                '3': 'Aperture Priority Mode',  # Ваш текущий режим
                '4': 'Auto Mode (Constant Shutter)'
            }
            mode_str = modes.get(mode_val, f'Unknown ({mode_val})')
            
            # Получить выдержку
            result = subprocess.run([
                'v4l2-ctl', '-d', f'/dev/video{self.device_id}',
                '--get-ctrl', 'exposure_time_absolute'
            ], capture_output=True, text=True)
            
            exposure = result.stdout.strip().split(':')[-1].strip()
            
            print(f"  Режим: {mode_str}")
            print(f"  Выдержка: {exposure} мкс ({int(exposure)/1000:.2f} мс)")
            
            # Проверка на максимальную выдержку
            if DEFAULT_FPS > 0:
                max_exposure = 1000000 // DEFAULT_FPS
                if int(exposure) > max_exposure:
                    print(f"  ⚠️ Выдержка превышает период кадра при {DEFAULT_FPS} fps!")
            
        except Exception as e:
            print(f"  ❌ Не удалось получить информацию: {e}")
    
    def set_exposure(self, exposure_time_us=None, mode='manual'):
        """
        Установка параметров экспозиции камеры
        
        Args:
            exposure_time_us: выдержка в микросекундах (1-10000 для вашей камеры)
            mode: 'auto' или 'manual'
        """
        print("\n📸 НАСТРОЙКА ЭКСПОЗИЦИИ")
        
        try:
            if mode == 'manual' and exposure_time_us:
                # Включить ручной режим (auto_exposure=1 для Manual Mode)
                subprocess.run([
                    'v4l2-ctl', '-d', f'/dev/video{self.device_id}',
                    '-c', 'auto_exposure=1'  # 1 = Manual Mode
                ], check=True)
                
                # Установить выдержку (в микросекундах, от 1 до 10000)
                # Проверяем, что значение в допустимых пределах
                exposure_value = max(1, min(exposure_time_us, 10000))
                
                subprocess.run([
                    'v4l2-ctl', '-d', f'/dev/video{self.device_id}',
                    '-c', f'exposure_time_absolute={exposure_value}'
                ], check=True)
                
                print(f"  ✅ Ручной режим: выдержка {exposure_value} мкс ({exposure_value/1000:.2f} мс)")
                
                # Проверка максимальной выдержки для текущего FPS
                if DEFAULT_FPS > 0:
                    max_exposure = 1000000 // DEFAULT_FPS  # макс выдержка в мкс
                    if exposure_value > max_exposure:
                        print(f"  ⚠️ ВНИМАНИЕ: Выдержка {exposure_value} мкс превышает период кадра {max_exposure} мкс при {DEFAULT_FPS} fps")
                        print(f"     Это может привести к пропуску кадров!")
            
            elif mode == 'auto':
                # Автоматический режим (auto_exposure=3 для Aperture Priority Mode)
                subprocess.run([
                    'v4l2-ctl', '-d', f'/dev/video{self.device_id}',
                    '-c', 'auto_exposure=3'  # 3 = Aperture Priority Mode
                ], check=True)
                print("  ✅ Автоматический режим экспозиции (Aperture Priority)")
            
            # Показать текущие настройки
            self.get_exposure_info()
            
        except Exception as e:
            print(f"  ❌ Ошибка настройки экспозиции: {e}")

    def test_resolution_optimized(self, backend, width, height, target_fps, duration=10):
        """
        Тестирование с поддержкой различных оптимизаций
        """
        # Определяем, какие оптимизации включены
        use_baseline = USE_BASELINE
        use_ring = USE_RING_BUFFER and not use_baseline
        use_threading = USE_THREADING and not use_baseline
        use_numpy = USE_NUMPY_PREALLOC and not use_baseline
        
        if USE_ALL_OPTIMIZATIONS:
            use_ring = use_threading = use_numpy = True
            use_baseline = False
        
        # Формируем имя теста с информацией об оптимизациях
        opt_names = []
        if use_baseline: opt_names.append("BASELINE")
        if use_ring: opt_names.append("RING")
        if use_threading: opt_names.append("THREAD")
        if use_numpy: opt_names.append("NUMPY")
        opt_str = "+".join(opt_names) if opt_names else "NO_OPT"
        
        mode_str = "STATS_ONLY" if STATS_ONLY_MODE else "FULL_CAPTURE"
        test_name = f"{mode_str}_{opt_str}_{backend}_{width}x{height}_{target_fps}fps"
        
        # Начинаем логирование
        log_file = self.logger.start_logging(test_name)
        old_stdout = sys.stdout
        sys.stdout = self.logger
        
        try:
            print(f"\n{'#'*80}")
            print(f"📊 РЕЖИМ: {'Статистика' if STATS_ONLY_MODE else 'Полный'}")
            print(f"🔧 ОПТИМИЗАЦИИ: {opt_str}")
            print(f"🎥 ТЕСТ: {backend} | {width}x{height} | {target_fps} fps | {duration} сек")
            print(f"{'#'*80}")
            
            # Инициализация камеры
            cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)
            
            # Настройка экспозиции (НОВОЕ)
            if EXPOSURE_MODE == 'manual':
                self.set_exposure(exposure_time_us=EXPOSURE_TIME_US, mode='manual')
            else:
                self.set_exposure(mode='auto')

            if backend.upper() == 'MJPEG':
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            else:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, target_fps)
            
            time.sleep(1)
            
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            print(f"\n📊 Реальные параметры: {actual_width}x{actual_height}")
            
            if actual_width != width or actual_height != height:
                print(f"❌ Размер не поддерживается")
                cap.release()
                return False
            
            # ВЫБОР РЕЖИМА РАБОТЫ
            if use_threading and not STATS_ONLY_MODE:
                # Многопоточный режим (только для полного захвата)
                return self._run_threaded_capture(cap, backend, actual_width, actual_height, 
                                                  target_fps, duration, opt_str, test_name)
            else:
                # Однопоточный режим с буферами
                return self._run_single_thread_capture(cap, backend, actual_width, actual_height,
                                                       target_fps, duration, opt_str, test_name,
                                                       use_ring, use_numpy)
        
        finally:
            sys.stdout = old_stdout
            self.logger.stop_logging()
    
    def _run_single_thread_capture(self, cap, backend, width, height, target_fps, 
                                   duration, opt_str, test_name, use_ring, use_numpy):
        """Однопоточный захват с буферами"""
        
        # Инициализация буфера
        if use_numpy and not STATS_ONLY_MODE:
            # Pre-allocated numpy массив
            buffer_size = int(target_fps * NUMPY_BUFFER_SECONDS)
            frame_buffer = NumpyPreallocBuffer(buffer_size, width, height)
            print(f"  Используется numpy буфер на {buffer_size} кадров")
        elif use_ring and not STATS_ONLY_MODE:
            # Кольцевой буфер
            frame_buffer = RingBuffer(RING_BUFFER_SIZE, width, height)
            print(f"  Используется кольцевой буфер на {RING_BUFFER_SIZE} кадров")
        else:
            # Обычный список (baseline)
            frame_buffer = [] if not STATS_ONLY_MODE else None
        
        # Статистика
        frame_count = 0
        start_time = time.time()
        fps_log = []
        last_log_time = start_time
        bytes_processed = 0
        
        print(f"\n⏱️  Захват {duration} секунд...")
        
        try:
            while time.time() - start_time < duration:
                ret, frame = cap.read()
                
                if ret:
                    frame_count += 1
                    
                    if STATS_ONLY_MODE:
                        bytes_processed += frame.nbytes
                    else:
                        if use_numpy:
                            frame_buffer.add_frame(frame)
                        elif use_ring:
                            frame_buffer.add_frame(frame)
                        else:
                            frame_buffer.append(frame.copy())
                        bytes_processed += frame.nbytes
                    
                    # Логирование
                    current_time = time.time()
                    if current_time - last_log_time >= 2.0:
                        elapsed = current_time - start_time
                        current_fps = frame_count / elapsed
                        fps_log.append(current_fps)
                        
                        mb_per_sec = (bytes_processed / (1024 * 1024)) / elapsed
                        gbits_per_sec = (bytes_processed * 8) / (1000 * 1000 * 1000) / elapsed
                        
                        mode_indicator = "📊" if STATS_ONLY_MODE else "💾"
                        print(f"  {mode_indicator} Сек {int(elapsed)}: {current_fps:.2f} fps | "
                              f"{mb_per_sec:.2f} МБ/с ({gbits_per_sec:.2f} Гбит/с) | кадров: {frame_count}")
                        
                        if not STATS_ONLY_MODE and not use_numpy and not use_ring:
                            mem_usage = len(frame_buffer) * frame.nbytes / (1024 * 1024)
                            print(f"     RAM: {mem_usage:.1f} MB")
                        
                        last_log_time = current_time
                else:
                    print("⚠️  Пропуск кадра")
                    time.sleep(0.001)
        
        finally:
            total_time = time.time() - start_time
            actual_fps = frame_count / total_time
            
            # Сохранение видео
            if not STATS_ONLY_MODE and frame_count > 0:
                filename = f"{self.output_dir}/{opt_str}_{backend}_{width}x{height}_{target_fps}fps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
                
                if backend.upper() == 'MJPEG':
                    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                else:
                    fourcc = cv2.VideoWriter_fourcc(*'FFV1')
                
                print(f"\n📝 Сохранение видео с FPS = {actual_fps:.2f}...")
                writer = cv2.VideoWriter(filename, fourcc, actual_fps, (width, height))
                
                if use_numpy or use_ring:
                    frames_to_write = frame_buffer.get_all_frames()
                    for i, f in enumerate(frames_to_write):
                        if f is not None:
                            writer.write(f)
                            if (i + 1) % 50 == 0:
                                print(f"  Записано: {i + 1}/{len(frames_to_write)}")
                else:
                    for i, f in enumerate(frame_buffer):
                        writer.write(f)
                        if (i + 1) % 50 == 0:
                            print(f"  Записано: {i + 1}/{len(frame_buffer)}")
                
                writer.release()
                print(f"✅ Видео сохранено: {filename}")
            
            cap.release()
            
            # Итоговая статистика
            mb_per_sec = (bytes_processed / (1024 * 1024)) / total_time
            gbits_per_sec = (bytes_processed * 8) / (1000 * 1000 * 1000) / total_time
            
            print(f"\n📊 ИТОГИ ТЕСТА [{opt_str}]:")
            print(f"  Кадров: {frame_count}")
            print(f"  Время: {total_time:.2f} сек")
            print(f"  FPS: {actual_fps:.2f}")
            print(f"  Целевой FPS: {target_fps}")
            print(f"  Эффективность: {(actual_fps/target_fps)*100:.1f}%")
            print(f"  Поток: {mb_per_sec:.2f} МБ/с ({gbits_per_sec:.2f} Гбит/с)")
            
            if fps_log:
                print(f"  Макс FPS: {max(fps_log):.2f}")
                print(f"  Мин FPS: {min(fps_log):.2f}")
            
            return True
    
    def _run_threaded_capture(self, cap, backend, width, height, target_fps, 
                            duration, opt_str, test_name):
        """Многопоточный захват с очередью"""
        
        # Закрываем переданный cap, так как ThreadedCapture откроет свой
        cap.release()
        
        # Создаем и запускаем поток захвата
        threaded_cap = ThreadedCapture(
            device_id=self.device_id,
            backend=backend,
            width=width,
            height=height,
            target_fps=target_fps,
            queue_size=QUEUE_SIZE
        )
        
        print(f"  Запуск многопоточного захвата с device_id={self.device_id}...")
        success = threaded_cap.start()
        
        # Даем время на инициализацию
        time.sleep(1)
        
        # Проверяем, что захват работает
        test_frame = None
        for _ in range(10):  # Пробуем несколько раз
            test_frame = threaded_cap.get_frame(timeout=0.5)
            if test_frame is not None:
                break
            time.sleep(0.1)
        
        if test_frame is None:
            print("❌ Не удалось получить первый кадр в многопоточном режиме")
            stats = threaded_cap.get_stats()
            if stats['error']:
                print(f"   Ошибка: {stats['error']}")
            threaded_cap.stop()
            return False
        
        print(f"✅ Многопоточный захват работает (первый кадр получен)")
        
        # Буфер для кадров (кольцевой или numpy)
        use_numpy = USE_NUMPY_PREALLOC
        use_ring = USE_RING_BUFFER and not use_numpy
        
        if use_numpy:
            buffer_size = int(target_fps * NUMPY_BUFFER_SECONDS)
            frame_buffer = NumpyPreallocBuffer(buffer_size, width, height)
            print(f"  Многопоточный режим + numpy буфер на {buffer_size} кадров")
        elif use_ring:
            frame_buffer = RingBuffer(RING_BUFFER_SIZE, width, height)
            print(f"  Многопоточный режим + кольцевой буфер на {RING_BUFFER_SIZE} кадров")
        else:
            frame_buffer = []
            print(f"  Многопоточный режим + список")
        
        # Статистика
        frame_count = 0
        start_time = time.time()
        fps_log = []
        last_log_time = start_time
        bytes_processed = 0
        
        print(f"\n⏱️  Захват {duration} секунд...")
        
        try:
            while time.time() - start_time < duration:
                frame = threaded_cap.get_frame(timeout=0.5)
                
                if frame is not None:
                    frame_count += 1
                    
                    if use_numpy:
                        frame_buffer.add_frame(frame)
                    elif use_ring:
                        frame_buffer.add_frame(frame)
                    else:
                        frame_buffer.append(frame.copy())
                    
                    bytes_processed += frame.nbytes
                    
                    # Логирование каждые 2 секунды
                    current_time = time.time()
                    if current_time - last_log_time >= 2.0:
                        elapsed = current_time - start_time
                        current_fps = frame_count / elapsed
                        fps_log.append(current_fps)
                        
                        mb_per_sec = (bytes_processed / (1024 * 1024)) / elapsed
                        gbits_per_sec = (bytes_processed * 8) / (1000 * 1000 * 1000) / elapsed
                        stats = threaded_cap.get_stats()
                        
                        print(f"  🧵 Сек {int(elapsed)}: {current_fps:.2f} fps | "
                            f"{mb_per_sec:.2f} МБ/с ({gbits_per_sec:.2f} Гбит/с) | "
                            f"кадров: {frame_count} | дроп: {stats['dropped']} | "
                            f"очередь: {stats['queue_size']}")
                        
                        last_log_time = current_time
                else:
                    # Если нет кадров больше 2 секунд - возможно проблема
                    if time.time() - start_time > 2 and frame_count == 0:
                        print("❌ Нет кадров в течение 2 секунд")
                        break
                    
        except Exception as e:
            print(f"❌ Ошибка во время захвата: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            threaded_cap.stop()
            total_time = time.time() - start_time
            actual_fps = frame_count / total_time if total_time > 0 else 0
            stats = threaded_cap.get_stats()
            
            # Сохранение видео
            if frame_count > 0:
                filename = f"{self.output_dir}/{opt_str}_THREAD_{backend}_{width}x{height}_{target_fps}fps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
                
                if backend.upper() == 'MJPEG':
                    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                else:
                    fourcc = cv2.VideoWriter_fourcc(*'FFV1')
                
                print(f"\n📝 Сохранение видео с FPS = {actual_fps:.2f}...")
                writer = cv2.VideoWriter(filename, fourcc, actual_fps, (width, height))
                
                if writer.isOpened():
                    if use_numpy or use_ring:
                        frames_to_write = frame_buffer.get_all_frames()
                        # Фильтруем None значения
                        valid_frames = [f for f in frames_to_write if f is not None]
                        for i, f in enumerate(valid_frames):
                            writer.write(f)
                            if (i + 1) % 50 == 0:
                                print(f"  Записано: {i + 1}/{len(valid_frames)}")
                    else:
                        for i, f in enumerate(frame_buffer):
                            writer.write(f)
                            if (i + 1) % 50 == 0:
                                print(f"  Записано: {i + 1}/{len(frame_buffer)}")
                    
                    writer.release()
                    print(f"✅ Видео сохранено: {filename}")
                    
                    # Проверка размера файла
                    if os.path.exists(filename):
                        size_mb = os.path.getsize(filename) / (1024 * 1024)
                        print(f"  Размер файла: {size_mb:.2f} MB")
                else:
                    print("❌ Не удалось создать VideoWriter")
            else:
                print("❌ Нет кадров для сохранения")
            
            # Итоговая статистика
            mb_per_sec = (bytes_processed / (1024 * 1024)) / total_time if total_time > 0 else 0
            gbits_per_sec = (bytes_processed * 8) / (1000 * 1000 * 1000) / total_time if total_time > 0 else 0
            
            print(f"\n📊 ИТОГИ ТЕСТА [{opt_str}+THREAD]:")
            print(f"  Кадров захвачено: {stats['captured']}")
            print(f"  Кадров обработано: {frame_count}")
            print(f"  Дропнуто: {stats['dropped']}")
            print(f"  Время: {total_time:.2f} сек")
            print(f"  FPS обработки: {actual_fps:.2f}")
            if target_fps > 0:
                print(f"  Целевой FPS: {target_fps}")
                print(f"  Эффективность: {(actual_fps/target_fps)*100:.1f}%")
            print(f"  Поток: {mb_per_sec:.2f} МБ/с ({gbits_per_sec:.2f} Гбит/с)")
            
            return frame_count > 0
    
    # Для обратной совместимости оставляем старую функцию
    def test_resolution(self, backend, width, height, target_fps, duration=10):
        """Обертка для совместимости - вызывает оптимизированную версию"""
        return self.test_resolution_optimized(backend, width, height, target_fps, duration)
    
    def run_default_test(self):
        """Запуск теста с параметрами по умолчанию"""
        print("\n" + "="*80)
        print("🚀 ЗАПУСК В РЕЖИМЕ ПО УМОЛЧАНИЮ")
        print("="*80)
        print(f"Бэкенд: {DEFAULT_BACKEND}")
        print(f"Разрешение: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        print(f"Целевой FPS: {DEFAULT_FPS}")
        print(f"Длительность: {DEFAULT_DURATION} сек")
        print("="*80)
        
        self.test_resolution_optimized(
            backend=DEFAULT_BACKEND,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            target_fps=DEFAULT_FPS,
            duration=DEFAULT_DURATION
        )
    
    def run_single_test(self):
        """Запуск одного выбранного теста"""
        print("\n" + "="*80)
        print("🎯 ВЫБОР ОДНОГО РЕЖИМА ТЕСТИРОВАНИЯ")
        print("="*80)
        
        # Выбор бэкенда
        print("\nВыберите бэкенд (формат):")
        print("1. MJPEG (сжатый)")
        print("2. YUYV (несжатый)")
        backend_choice = input("Ваш выбор (1-2): ").strip()
        backend = 'MJPEG' if backend_choice == '1' else 'YUYV'
        
        # Выбор разрешения
        print("\nВыберите разрешение:")
        resolutions = {
            '1': (1920, 1200, '1920x1200 (Max)'),
            '2': (1280, 720, '1280x720 (720p)'),
            '3': (640, 480, '640x480 (VGA)'),
            '4': (320, 240, '320x240 (QVGA)')
        }
        
        for key, (w, h, name) in resolutions.items():
            print(f"{key}. {name}")
        
        res_choice = input("Ваш выбор (1-4): ").strip()
        if res_choice not in resolutions:
            print("❌ Неверный выбор, используем 640x480")
            width, height = 640, 480
        else:
            width, height = resolutions[res_choice][0], resolutions[res_choice][1]
        
        # Выбор FPS
        print("\nВведите целевой FPS (например: 30, 60, 90, 120):")
        try:
            target_fps = int(input("FPS: ").strip())
        except ValueError:
            print("❌ Неверное значение, используем 30 fps")
            target_fps = 30
        
        # Выбор длительности
        print("\nВведите длительность записи в секундах:")
        try:
            duration = float(input("Длительность (сек): ").strip())
            if duration <= 0:
                duration = 10
                print("⚠️ Длительность должна быть > 0, используем 10 сек")
        except ValueError:
            duration = 10
            print("⚠️ Неверное значение, используем 10 сек")
        
        # Запуск теста
        print(f"\n🚀 Запуск теста: {backend} | {width}x{height} | {target_fps} fps | {duration} сек")
        confirm = input("Подтвердить? (y/n): ").strip().lower()
        
        if confirm == 'y':
            self.test_resolution_optimized(backend, width, height, target_fps, duration)
        else:
            print("❌ Тест отменен")
    
    def run_all_tests(self, short_test=False):
        """
        Запуск всех тестов
        
        Args:
            short_test: если True, записывать по 5 секунд вместо 10
        """
        duration = 5 if short_test else 10
        
        print("\n" + "="*80)
        print("🚀 ЗАПУСК ТЕСТОВ ЗАХВАТА ВИДЕО")
        print(f"Длительность каждого теста: {duration} секунд")
        print("="*80)
        
        results = []
        
        for i, mode in enumerate(TEST_MODES, 1):
            print(f"\n{'#'*80}")
            print(f"ТЕСТ #{i}: {mode['name']}")
            print(f"{'#'*80}")
            
            success = self.test_resolution_optimized(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
            
            results.append({
                'test': mode['name'],
                'success': success,
                'backend': mode['backend'],
                'resolution': f"{mode['width']}x{mode['height']}",
                'target_fps': mode['fps']
            })
            
            # Пауза между тестами
            time.sleep(2)
        
        # Выводим сводку
        print("\n" + "="*80)
        print("📊 СВОДКА РЕЗУЛЬТАТОВ")
        print("="*80)
        
        for result in results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['resolution']} @ {result['target_fps']}fps")
        
        print(f"\n📁 Все видео сохранены в директории: {self.output_dir}")
        print("="*80)
    
    def run_mjpeg_only(self, duration):
        """Запуск только MJPEG тестов"""
        print("\n" + "="*80)
        print("🚀 ЗАПУСК MJPEG ТЕСТОВ")
        print(f"Длительность каждого теста: {duration} секунд")
        print("="*80)
        
        for mode in MJPEG_ONLY_MODES:
            self.test_resolution_optimized(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
            time.sleep(2)
    
    def run_yuyv_only(self, duration):
        """Запуск только YUYV тестов"""
        print("\n" + "="*80)
        print("🚀 ЗАПУСК YUYV ТЕСТОВ")
        print(f"Длительность каждого теста: {duration} секунд")
        print("="*80)
        
        for mode in YUYV_ONLY_MODES:
            self.test_resolution_optimized(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
            time.sleep(2)
    
    def cleanup_old_videos(self, days=7):
        """Удаление старых видеофайлов"""
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        count = 0
        
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.isfile(filepath):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if mtime < cutoff:
                    os.remove(filepath)
                    count += 1
                    print(f"Удален старый файл: {filename}")
        
        print(f"\n✅ Удалено {count} файлов")


# ============================================================
# ФУНКЦИИ ДЛЯ ЗАПУСКА
# ============================================================

def print_optimization_help():
    """Вывод информации об оптимизациях"""
    print("\n" + "="*80)
    print("🔧 ДОСТУПНЫЕ ОПТИМИЗАЦИИ")
    print("="*80)
    print("В шапке скрипта можно настроить:")
    print("\n  USE_BASELINE = True     # Базовый режим (как в оригинале)")
    print("  USE_RING_BUFFER = True   # Кольцевой буфер (меньше аллокаций)")
    print("  USE_THREADING = True     # Многопоточный захват")
    print("  USE_NUMPY_PREALLOC = True # Pre-allocated numpy массив")
    print("  USE_ALL_OPTIMIZATIONS = True # Включить всё")
    print("\n📊 Сравнение результатов будет в логах")

def main():
    """Основная функция"""
    
    if RUN_DEFAULT:
        tester = VideoCaptureTester(device_id=DEVICE_ID, output_dir=OUTPUT_DIR, log_dir=LOGS_DIR)
        tester.get_camera_info()
        print_optimization_help()
        tester.run_default_test()
        return
    
    # Проверка аргументов командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == "--default":
            # Режим по умолчанию - без меню
            tester = VideoCaptureTester(device_id=DEVICE_ID, output_dir=OUTPUT_DIR, log_dir=LOGS_DIR)
            tester.get_camera_info()
            tester.run_default_test()
            return
        elif sys.argv[1] == "--help":
            print_usage()
            return
    
    # Интерактивный режим с меню
    print("\n" + "="*80)
    print("🎬 ТЕСТОВЫЙ ЗАХВАТ ВИДЕО С КАМЕРЫ ГЛОБАЛЬНОГО ЗАТВОРА")
    print("="*80)
    
    # Создаем тестер
    tester = VideoCaptureTester(device_id=DEVICE_ID, output_dir=OUTPUT_DIR, log_dir=LOGS_DIR)
    
    # Получаем информацию о камере
    tester.get_camera_info()
    
    # Спрашиваем режим тестирования
    print("\n" + "="*80)
    print("📋 МЕНЮ ТЕСТИРОВАНИЯ")
    print("="*80)
    print("1. Полное тестирование (10 сек на режим)")
    print("2. Быстрое тестирование (5 сек на режим)")
    print("3. Только MJPEG режимы")
    print("4. Только YUYV режимы")
    print("5. Один режим (свой выбор)")
    print("6. Очистка старых видео")
    print("7. Режим только статистика (быстрый тест)")
    print("8. Сравнение: полный vs статистика")    
    print("\nСовет: для запуска без меню используйте:")
    print("  python3 camera_test.py --default")
    print("  или установите RUN_DEFAULT = True в шапке скрипта")
    
    choice = input("\nВаш выбор (1-6) [по умолчанию 2]: ").strip() or "2"
    
    if choice == "1":
        tester.run_all_tests(short_test=False)
    elif choice == "2":
        tester.run_all_tests(short_test=True)
    elif choice == "3":
        print("\nВведите длительность записи для каждого режима (сек):")
        try:
            duration = float(input("Длительность [10]: ").strip() or "10")
        except ValueError:
            duration = 10
            print(f"⚠️ Используем {duration} сек")
        tester.run_mjpeg_only(duration)
    elif choice == "4":
        print("\nВведите длительность записи для каждого режима (сек):")
        try:
            duration = float(input("Длительность [10]: ").strip() or "10")
        except ValueError:
            duration = 10
            print(f"⚠️ Используем {duration} сек")
        tester.run_yuyv_only(duration)
    elif choice == "5":
        tester.run_single_test()
    elif choice == "6":
        try:
            days = int(input("Удалить файлы старше N дней [7]: ").strip() or "7")
            tester.cleanup_old_videos(days)
        except ValueError:
            tester.cleanup_old_videos(7)

    if choice == "7":
        # Временно включаем режим статистики
        global STATS_ONLY_MODE
        old_mode = STATS_ONLY_MODE
        STATS_ONLY_MODE = True
        tester.run_default_test()  # или другой тест
        STATS_ONLY_MODE = old_mode            
    
    print(f"\n✅ Все тесты завершены!")
    print(f"📁 Видео сохранены в: {OUTPUT_DIR}")
    print(f"📁 Логи сохранены в: {LOGS_DIR}")
    print("\nДля анализа видео можно использовать:")
    print("  ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of default=noprint_wrappers=1:nokey=1 файл.avi")
    print("  ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 файл.avi")
    print("  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 файл.avi")

if __name__ == "__main__":
    main()