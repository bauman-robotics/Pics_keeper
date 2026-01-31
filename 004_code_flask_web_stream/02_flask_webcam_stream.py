#!/usr/bin/env python3
"""
Flask Web Server for Webcam Streaming - Version 4
YAML Configuration Support
"""
# 02_flask_webcam_stream.py

import yaml
import cv2
import sys
import threading
import time
import queue
import copy
import os
import numpy as np
from flask import Flask, Response, render_template, jsonify, request
import argparse
from utils.camera_checker import CameraChecker

# Импортируем логгер
from utils.logger import create_logger

def load_config(config_path="config.yaml"):
    """Загрузка конфигурации из YAML файла"""
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            print(f"✅ Конфигурация загружена из {config_path}")
            return config
    except FileNotFoundError:
        print(f"❌ Файл конфигурации не найден: {config_path}")
        print("Используйте --config для указания пути к конфигурационному файлу")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Ошибка парсинга YAML: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

def get_camera_backend(backend_name):
    """Получение бэкенда OpenCV по имени"""
    backends = {
        "default": None,
        "v4l2": cv2.CAP_V4L2,
        "ffmpeg": cv2.CAP_FFMPEG,
        "direct": cv2.CAP_V4L2  # Для прямого доступа используем V4L2
    }
    return backends.get(backend_name.lower(), None)

def test_camera_backends(config, logger):
    """Тестируем разные способы открытия камеры согласно конфигурации"""
    
    camera_config = config['camera']
    backend_mode = camera_config['backend'].lower()
    
    if backend_mode == "auto":
        # Автоматическое тестирование бэкендов
        backends = []
        for backend_name in camera_config['test_backends']:
            if backend_name == "default":
                backends.append(("Default", camera_config['device'], None))
            elif backend_name == "v4l2_video0":
                backends.append(("V4L2 video0", 0, cv2.CAP_V4L2))
            elif backend_name == "v4l2_video1":
                backends.append(("V4L2 video1", 1, cv2.CAP_V4L2))
            elif backend_name == "ffmpeg_video0":
                backends.append(("FFMPEG video0", 0, cv2.CAP_FFMPEG))
            elif backend_name == "direct_video0":
                backends.append(("Direct /dev/video0", "/dev/video0", cv2.CAP_V4L2))
            elif backend_name == "direct_video1":
                backends.append(("Direct /dev/video1", "/dev/video1", cv2.CAP_V4L2))
    else:
        # Конкретный бэкенд
        backend = get_camera_backend(backend_mode)
        if backend_mode == "direct":
            device = camera_config['direct_path']
        else:
            device = camera_config['device']
        backends = [(f"Config: {backend_mode}", device, backend)]
    
    for name, device, backend in backends:
        print(f"\nПробую {name}...")
        try:
            if backend is None:
                cam = cv2.VideoCapture(device)
            else:
                cam = cv2.VideoCapture(device, backend)
            
            # Устанавливаем разрешение если указано
            if 'width' in camera_config and 'height' in camera_config:
                cam.set(cv2.CAP_PROP_FRAME_WIDTH, camera_config['width'])
                cam.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_config['height'])
            
            # Устанавливаем FPS если указано
            if 'fps' in camera_config:
                cam.set(cv2.CAP_PROP_FPS, camera_config['fps'])
            
            if cam.isOpened():
                ret, frame = cam.read()
                if ret and frame is not None:
                    actual_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = int(cam.get(cv2.CAP_PROP_FPS))
                    
                    resolution_str = f"{actual_width}x{actual_height}"
                    fps_str = f"{actual_fps}"
                    
                    print(f"✅ {name} РАБОТАЕТ!")
                    print(f"   Разрешение: {resolution_str}")
                    print(f"   FPS: {fps_str}")
                    
                    # Логируем успешное подключение
                    logger.log_camera_test(name, True, resolution_str, fps_str)
                    
                    # Сохраняем информацию о найденной камере
                    camera_info = {
                        'name': name,
                        'resolution': resolution_str,
                        'fps': fps_str
                    }
                    # Передаем информацию о камере в логирование запуска
                    logger.log_startup_info(config, camera_info)
                    
                    return cam
                else:
                    print(f"⚠️  {name} открылась, но не может читать кадры")
                    logger.log_camera_test(name, False, error="Не может читать кадры")
                    cam.release()
            else:
                print(f"❌ {name} не открылась")
                logger.log_camera_test(name, False, error="Не удалось открыть устройство")
                cam.release()
        except Exception as e:
            print(f"❌ {name} ошибка: {e}")
            logger.log_camera_test(name, False, error=str(e))
    
    return None

class CameraStreamer:
    """Класс для управления камерой и стримингом"""
    
    def __init__(self, config, logger, camera):
        self.config = config
        self.logger = logger
        self.current_camera = camera
        
        # Состояние стрима
        self.stream_active = False
        self.buffer_active = False
        self.frame_count = 0
        
        # Буферизация
        self.frame_buffer = queue.Queue(maxsize=30)
        self.camera_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.last_frame = None
        self.buffer_thread = None
        
        # Управление подключениями
        self.active_streams = 0
        self.MAX_CONCURRENT_STREAMS = config['server'].get('max_concurrent_streams', 4)
        self.stream_lock = threading.Lock()
        
        # Словарь для отслеживания активных соединений
        self.active_clients = {}
        self.MAX_STREAMS_PER_CLIENT = 1
        
        # Определяем путь к шаблонам
        templates_folder = config.get('paths', {}).get('templates_folder', 'templates')
        
        # Полный путь к шаблонам
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_templates_path = os.path.join(current_dir, templates_folder)
        
        # Проверяем существование папки
        if not os.path.exists(full_templates_path):
            print(f"⚠️  Папка шаблонов не найдена: {full_templates_path}")
            print(f"   Создаю папку {full_templates_path}")
            os.makedirs(full_templates_path, exist_ok=True)
            
            # Создаем простой index.html если его нет
            index_path = os.path.join(full_templates_path, 'index.html')
            if not os.path.exists(index_path):
                with open(index_path, 'w') as f:
                    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Webcam Stream</title>
</head>
<body>
    <h1>🎥 Webcam Stream</h1>
    <div id="status">Сервер работает!</div>
    <a href="/status">Статус</a> | 
    <a href="/logs">Логи</a>
</body>
</html>''')
        
        print(f"📁 Папка шаблонов: {full_templates_path}")
        
        # Инициализация Flask с абсолютным путем
        self.app = Flask(__name__, template_folder=full_templates_path)
        
        # Настройка маршрутов
        self.setup_routes()
        
        # Сканируем доступные камеры
        try:
            self.camera_checker = CameraChecker(logger=self.logger)
            self.available_cameras = self.camera_checker.detect_cameras()
        except Exception as e:
            print(f"⚠️  Ошибка сканирования камер: {e}")
            self.available_cameras = []
        
        # Добавляем отслеживание времени активности стримов
        self.stream_sessions = {}  # client_id -> timestamp
        
        # Таймер для очистки старых стримов
        self.cleanup_timer = threading.Timer(30.0, self.cleanup_old_streams)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
        
        print(f"✅ CameraStreamer инициализирован")

        # Кэш для списка камер
        self.cameras_cache = None
        self.cameras_cache_time = 0
        self.CAMERAS_CACHE_TTL = 30  # секунд



    def cleanup_old_streams(self):
        """Очистка старых стримов"""
        with self.stream_lock:
            current_time = time.time()
            # Удаляем стримы старше 10 секунд
            old_streams = [cid for cid, ts in self.stream_sessions.items() 
                          if current_time - ts > 10.0]
            
            for client_id in old_streams:
                if self.active_streams > 0:
                    self.active_streams -= 1
                del self.stream_sessions[client_id]
                
            if old_streams:
                print(f"🧹 Очищено {len(old_streams)} старых стримов")
    
        # Перезапускаем таймер
        self.cleanup_timer = threading.Timer(30.0, self.cleanup_old_streams)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()

    def get_client_info(self):
        """Получение информации о клиенте"""
        if hasattr(request, 'remote_addr'):
            user_ip = request.remote_addr
        else:
            user_ip = 'unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')
        return user_ip, user_agent
    
    def capture_frames(self):
        """Захват кадров с камеры в буфер"""
        print(f"📹 Запущен поток захвата кадров (ID: {threading.get_ident()})")
        print(f"📊 Начальный размер буфера: {self.frame_buffer.qsize()}")
        
        self.buffer_active = True
        frames_captured = 0
        
        while self.stream_active and self.buffer_active:
            try:
                with self.camera_lock:
                    if self.current_camera and self.current_camera.isOpened():
                        ret, frame = self.current_camera.read()
                        if ret and frame is not None:
                            self.frame_count += 1
                            frames_captured += 1
                            
                            # Логируем каждые 30 кадров
                            if frames_captured % 30 == 0:
                                print(f"📊 Захвачено кадров: {frames_captured}, Размер буфера: {self.frame_buffer.qsize()}")
                            
                            # Сохраняем последний кадр
                            with self.frame_lock:
                                self.last_frame = frame.copy()
                            
                            # Добавляем в буфер с проверкой на переполнение
                            try:
                                # Если буфер полон, НЕ ОЧИЩАЕМ его полностью, а просто пропускаем старый кадр
                                if self.frame_buffer.full():
                                    # Удаляем только ОДИН старый кадр
                                    try:
                                        self.frame_buffer.get_nowait()
                                        if frames_captured % 30 == 0:
                                            print(f"🔄 Буфер полон, удален старый кадр")
                                    except queue.Empty:
                                        pass
                                
                                self.frame_buffer.put_nowait(frame)
                            except Exception as e:
                                print(f"⚠️ Ошибка буфера: {e}")
                        else:
                            if frames_captured % 10 == 0:  # Реже логируем ошибки
                                print(f"⚠️ Не удалось прочитать кадр (кадр {frames_captured})")
                            time.sleep(0.033)  # ~30 FPS
                    else:
                        if frames_captured % 10 == 0:
                            print(f"❌ Камера недоступна")
                        time.sleep(0.5)
            except Exception as e:
                if frames_captured % 10 == 0:
                    print(f"💥 Ошибка захвата: {e}")
                time.sleep(0.5)
        
        print(f"📹 Поток захвата кадров остановлен. Всего кадров: {frames_captured}")
    
    def generate_from_buffer(self):
        """Генератор для получения кадров из буфера"""
        while self.stream_active:
            try:
                # Получаем кадр из буфера с таймаутом
                frame = self.frame_buffer.get(timeout=2.0)
                
                # Кодируем в JPEG
                jpeg_quality = self.config['camera'].get('jpeg_quality', 85)
                ret, jpeg = cv2.imencode('.jpg', frame, 
                                         [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           jpeg.tobytes() + b'\r\n')
                else:
                    time.sleep(0.01)
                    
            except queue.Empty:
                # Если буфер пуст, ждем немного
                time.sleep(0.1)
            except Exception as e:
                self.logger.log_error(f"Ошибка в generate_from_buffer: {e}")
                time.sleep(0.1)
    
    def get_fallback_image(self):
        """Возвращает статичное изображение при перегрузке"""
        # Создаем простое изображение
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (40, 40, 40)  # Серый фон
        
        # Добавляем текст
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, 'Too many streams', (150, 200), font, 1, (255, 255, 255), 2)
        cv2.putText(img, 'Please try again later', (120, 250), font, 0.7, (200, 200, 200), 2)
        
        ret, buffer = cv2.imencode('.jpg', img)
        frame_bytes = buffer.tobytes()
        
        return Response(
            b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n',
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def start_stream_internal(self):
        """Внутренний запуск стрима"""
        if not self.stream_active:
            print("=== DEBUG: start_stream_internal() called ===")
            print(f"stream_active before: {self.stream_active}")
            print(f"📊 Размер буфера перед запуском: {self.frame_buffer.qsize()}")
            
            # ПРИНУДИТЕЛЬНЫЙ СБРОС БУФЕРА ПЕРЕД ЗАПУСКОМ
            if not self.frame_buffer.empty():
                print("⚠️ Буфер не пуст перед запуском, очищаем...")
                cleared = 0
                while not self.frame_buffer.empty():
                    try:
                        self.frame_buffer.get_nowait()
                        cleared += 1
                    except queue.Empty:
                        break
                print(f"✅ Очищено {cleared} элементов из буфера")
            
            self.stream_active = True
            self.buffer_active = True
            self.frame_count = 0
            
            # Убедимся, что старый поток завершен
            if self.buffer_thread and self.buffer_thread.is_alive():
                print("⚠️ Старый поток все еще активен, останавливаем...")
                self.buffer_active = False
                self.buffer_thread.join(timeout=1.0)
                self.buffer_thread = None
            
            # Запускаем новый поток захвата кадров
            self.buffer_thread = threading.Thread(target=self.capture_frames, daemon=True)
            self.buffer_thread.start()
            
            # Ждем немного чтобы поток успел стартовать
            time.sleep(0.1)
            
            print("✅ Стрим запущен")
            self.logger.log_info("Стрим видеопотока запущен")
            
            # Выводим состояние через 0.5 секунды
            def delayed_check():
                time.sleep(0.5)
                print(f"📊 Проверка через 0.5с: Поток жив: {self.buffer_thread.is_alive() if self.buffer_thread else False}, "
                    f"Буфер: {self.frame_buffer.qsize()}")
            
            threading.Thread(target=delayed_check, daemon=True).start()
    
    def stop_stream_internal(self):
        """Внутренняя остановка стрима"""
        if self.stream_active:
            print("=== DEBUG: stop_stream_internal() called ===")
            print(f"📊 Текущий размер буфера: {self.frame_buffer.qsize()}")
            
            # Сначала останавливаем захват
            self.stream_active = False
            self.buffer_active = False
            
            # Полностью очищаем буфер ПЕРЕД остановкой потока
            print("🧹 Очистка буфера...")
            buffer_items_cleared = 0
            while not self.frame_buffer.empty():
                try:
                    self.frame_buffer.get_nowait()
                    buffer_items_cleared += 1
                except queue.Empty:
                    break
            print(f"✅ Очищено элементов буфера: {buffer_items_cleared}")
            
            # Затем останавливаем поток
            if self.buffer_thread and self.buffer_thread.is_alive():
                print("⏳ Ожидание завершения потока захвата...")
                self.buffer_thread.join(timeout=2.0)
                if self.buffer_thread.is_alive():
                    print("⚠️ Поток захчета не завершился вовремя")
                self.buffer_thread = None
            
            print("📹 Стрим остановлен")
            self.logger.log_info("Стрим видеопотока остановлен")
        
    def restart_stream_async(self):
        """Асинхронный перезапуск стрима"""
        time.sleep(0.5)
        self.start_stream_internal()
    
    def setup_routes(self):
        """Настройка маршрутов Flask"""
        
        @self.app.before_request
        def log_request():
            """Логирование всех запросов"""
            if request.endpoint and request.endpoint not in ['static', 'video_feed']:
                user_ip, user_agent = self.get_client_info()
                self.logger.log_info(f"🌐 Запрос: {request.method} {request.path}")
        
        # ОБЯЗАТЕЛЬНО: Маршрут главной страницы
        @self.app.route('/')
        def index():
            """Главная страница"""
            try:
                return render_template('index.html')
            except Exception as e:
                return f'''
                <html>
                <head><title>Webcam Stream</title></head>
                <body>
                    <h1>🎥 Webcam Stream</h1>
                    <p>Сервер работает!</p>
                    <p>Шаблон не найден, создайте index.html в папке templates</p>
                    <p><a href="/status">Статус</a> | <a href="/logs">Логи</a></p>
                </body>
                </html>
                '''
        
        @self.app.route('/video_feed')
        def video_feed():
            """Маршрут для видео потока с ограничением"""
            # Получаем IP клиента
            client_ip = request.remote_addr if hasattr(request, 'remote_addr') else 'unknown'
            client_id = f"{client_ip}_{request.args.get('t', str(time.time()))}"
            
            with self.stream_lock:
                # Проверяем лимит для конкретного клиента
                client_streams = self.active_clients.get(client_ip, 0)
                if client_streams >= self.MAX_STREAMS_PER_CLIENT:
                    print(f"⚠️  Клиент {client_ip} уже имеет активный стрим")
                    return self.get_fallback_image()
                
                # Проверяем общий лимит
                if self.active_streams >= self.MAX_CONCURRENT_STREAMS:
                    print(f"⚠️  Превышено общее количество стримов: {self.active_streams}/{self.MAX_CONCURRENT_STREAMS}")
                    return self.get_fallback_image()
                
                # Увеличиваем счетчики
                self.active_streams += 1
                self.active_clients[client_ip] = client_streams + 1
                
                print(f"📹 Клиент {client_ip} запросил video_feed (клиентских: {client_streams+1}, всего: {self.active_streams})")
            
            def generate_with_cleanup():
                try:
                    for chunk in self.generate_from_buffer():
                        yield chunk
                except GeneratorExit:
                    print(f"📹 Клиент {client_ip} отключился")
                except Exception as e:
                    print(f"📹 Ошибка: {e}")
                finally:
                    with self.stream_lock:
                        # Уменьшаем счетчики
                        if self.active_streams > 0:
                            self.active_streams -= 1
                        
                        client_streams = self.active_clients.get(client_ip, 0)
                        if client_streams > 0:
                            self.active_clients[client_ip] = client_streams - 1
                            if self.active_clients[client_ip] <= 0:
                                del self.active_clients[client_ip]
                        
                        print(f"📹 Стрим завершен для {client_ip} (осталось: клиентских: {self.active_clients.get(client_ip,0)}, всего: {self.active_streams})")
            
            return Response(generate_with_cleanup(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
            
        @self.app.route('/api/stream/start', methods=['POST'])
        def start_stream():
            """Запуск видеопотока"""
            user_ip, user_agent = self.get_client_info()
            
            if not self.stream_active:
                # Проверяем камеру
                with self.camera_lock:
                    if self.current_camera is None or not self.current_camera.isOpened():
                        self.logger.log_web_action('start_stream', 'error', 'Camera not ready', user_ip, user_agent)
                        return jsonify({'status': 'error', 'message': 'Камера не готова'})
                
                self.start_stream_internal()
                
                self.logger.log_web_action('start_stream', 'success', 
                                        f"Stream started on {self.config['camera']['device']}",
                                        user_ip, user_agent)
                self.logger.log_button_click('start_stream', 'index', user_ip)
                return jsonify({'status': 'started', 'message': 'Видеопоток запущен'})
            else:
                self.logger.log_web_action('start_stream', 'warning', 'Stream already running',
                                        user_ip, user_agent)
                return jsonify({'status': 'already_running', 'message': 'Видеопоток уже запущен'})
        
        @self.app.route('/api/stream/stop', methods=['POST'])
        def stop_stream():
            """Остановка видеопотока"""
            user_ip, user_agent = self.get_client_info()
            
            if self.stream_active:
                self.stop_stream_internal()
                
                self.logger.log_web_action('stop_stream', 'success', 
                                        f"Stream stopped on {self.config['camera']['device']}",
                                        user_ip, user_agent)
                self.logger.log_button_click('stop_stream', 'index', user_ip)
                return jsonify({'status': 'stopped', 'message': 'Видеопоток остановлен'})
            else:
                self.logger.log_web_action('stop_stream', 'warning', 'Stream already stopped',
                                        user_ip, user_agent)
                return jsonify({'status': 'already_stopped', 'message': 'Видеопоток уже остановлен'})
        
        @self.app.route('/api/stream/status')
        def stream_status():
            """Получение статуса видеопотока"""
            # Проверяем состояние камеры с блокировкой
            camera_ready = False
            with self.camera_lock:
                if self.current_camera:
                    try:
                        camera_ready = self.current_camera.isOpened()
                    except:
                        camera_ready = False
            
            return jsonify({
                'stream_active': self.stream_active,
                'frame_count': self.frame_count,
                'camera_ready': camera_ready,
                'camera_device': self.config['camera']['device'],
                'config': {
                    'device': self.config['camera']['device'],
                    'backend': self.config['camera']['backend'],
                    'resolution': f"{self.config['camera'].get('width', 'auto')}x{self.config['camera'].get('height', 'auto')}",
                    'fps': self.config['camera'].get('fps', 'auto'),
                    'jpeg_quality': self.config['camera']['jpeg_quality']
                }
            })
        
        @self.app.route('/api/cameras')
        def get_cameras():
            """Получение списка доступных камер"""
            try:
                # Используем быстрый метод с кэшированием
                available_cameras = self.camera_checker.get_cameras_for_api()
                
                camera_list = []
                
                for cam in available_cameras:
                    # Если это не камера, пропускаем
                    if not cam.get('is_camera', False):
                        continue
                        
                    device_path = cam.get('device_path', '')
                    if not device_path:
                        continue
                    
                    camera_info = {
                        'device_path': device_path,
                        'name': cam.get('name', device_path),
                        'formats': cam.get('formats', [])[:2],  # Максимум 2 формата
                        'resolutions': cam.get('resolutions', [])[:3],  # Максимум 3 разрешения
                        'is_current': device_path == self.config['camera']['device']
                    }
                    
                    camera_list.append(camera_info)
                
                return jsonify({
                    'cameras': camera_list,
                    'total': len(camera_list),
                    'current_device': self.config['camera']['device']
                })
                
            except Exception as e:
                print(f"❌ Ошибка получения списка камер: {e}")
                # Возвращаем только текущую камеру
                return jsonify({
                    'cameras': [{
                        'device_path': self.config['camera']['device'],
                        'name': 'Текущая камера',
                        'formats': ['MJPG'],
                        'resolutions': ['640x480'],
                        'is_current': True
                    }],
                    'total': 1,
                    'current_device': self.config['camera']['device']
                })
        
        @self.app.route('/api/cameras/select', methods=['POST'])
        def select_camera():
            """Выбор камеры для стрима"""
            user_ip, user_agent = self.get_client_info()
            
            try:
                device_path = request.json.get('device_path')
                if not device_path:
                    self.logger.log_web_action('select_camera', 'error', 'No device path specified',
                                            user_ip, user_agent)
                    return jsonify({'status': 'error', 'message': 'Не указан путь к устройству'})
                
                # Получаем текущее состояние стрима
                was_streaming = self.stream_active
                
                # Если стрим активен, временно приостанавливаем захват кадров
                if self.stream_active:
                    self.buffer_active = False  # Приостанавливаем захват
                    if self.buffer_thread:
                        self.buffer_thread.join(timeout=1.0)
                    # Очищаем буфер
                    while not self.frame_buffer.empty():
                        try:
                            self.frame_buffer.get_nowait()
                        except queue.Empty:
                            break
                
                # Меняем камеру
                with self.camera_lock:
                    # Закрываем старую камеру
                    if self.current_camera:
                        try:
                            self.current_camera.release()
                            print("📹 Закрыта старая камера")
                        except Exception as e:
                            print(f"⚠️  Ошибка при закрытии камеры: {e}")
                    
                    # Открываем новую
                    try:
                        new_camera = cv2.VideoCapture(device_path)
                        if new_camera.isOpened():
                            # Настраиваем параметры
                            if 'width' in self.config['camera'] and 'height' in self.config['camera']:
                                new_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['camera']['width'])
                                new_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['camera']['height'])
                            
                            if 'fps' in self.config['camera']:
                                new_camera.set(cv2.CAP_PROP_FPS, self.config['camera']['fps'])
                            
                            self.current_camera = new_camera
                            self.config['camera']['device'] = device_path
                            self.frame_count = 0
                            
                            print(f"📹 Камера изменена на {device_path}")
                            self.logger.log_web_action('select_camera', 'success', 
                                                    f'Camera changed to {device_path}',
                                                    user_ip, user_agent)
                            
                            # Если стрим был активен, возобновляем захват
                            if was_streaming:
                                self.buffer_active = True
                                self.buffer_thread = threading.Thread(target=self.capture_frames, daemon=True)
                                self.buffer_thread.start()
                                print("📹 Захват кадров возобновлен с новой камеры")
                            
                            return jsonify({
                                'status': 'success', 
                                'message': f'Камера изменена на {device_path}',
                                'device_path': device_path,
                                'stream_active': was_streaming
                            })
                        else:
                            # Если не удалось открыть новую камеру
                            self.logger.log_web_action('select_camera', 'error', 
                                                    f'Failed to open camera {device_path}',
                                                    user_ip, user_agent)
                            return jsonify({'status': 'error', 'message': 'Не удалось открыть камеру'})
                            
                    except Exception as e:
                        self.logger.log_web_action('select_camera', 'error', 
                                                f'Exception during camera switch: {str(e)}',
                                                user_ip, user_agent)
                        return jsonify({'status': 'error', 'message': f'Ошибка при переключении камеры: {str(e)}'})
                        
            except Exception as e:
                self.logger.log_web_action('select_camera', 'error', f'Unexpected error: {str(e)}',
                                        user_ip, user_agent)
                return jsonify({'status': 'error', 'message': f'Неожиданная ошибка: {str(e)}'})
            
        @self.app.route('/status')
        def status_page():
            """Страница статуса сервера"""
            user_ip, user_agent = self.get_client_info()
            self.logger.log_web_action('page_load', 'success', 'Status page loaded', user_ip, user_agent)
            return render_template('status.html')
        
        @self.app.route('/logs')
        def logs_page():
            """Страница с логами"""
            user_ip, user_agent = self.get_client_info()
            self.logger.log_web_action('page_load', 'success', 'Logs page loaded', user_ip, user_agent)
            return render_template('logs.html')
        
        @self.app.route('/api/camera/test', methods=['GET'])
        def test_camera():
            """Тест камеры - попытка чтения кадра"""
            with self.camera_lock:
                if self.current_camera is None:
                    return jsonify({'status': 'error', 'message': 'Камера не инициализирована'})
                
                if not self.current_camera.isOpened():
                    return jsonify({'status': 'error', 'message': 'Камера не открыта'})
                
                success, frame = self.current_camera.read()
                if success and frame is not None:
                    # Пробуем получить параметры камеры
                    width = int(self.current_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(self.current_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(self.current_camera.get(cv2.CAP_PROP_FPS))
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Камера работает',
                        'resolution': f'{width}x{height}',
                        'fps': fps,
                        'frame_size': f'{frame.shape[1]}x{frame.shape[0]}' if frame is not None else None
                    })
                else:
                    return jsonify({'status': 'error', 'message': 'Не удалось прочитать кадр'})

        @self.app.route('/api/stream/diagnostics')
        def stream_diagnostics():
            """Диагностика состояния стрима"""
            return jsonify({
                'status': 'success',
                'diagnostics': self.get_stream_state_info()
            })

        @self.app.route('/api/stream/test_generator')
        def test_generator():
            """Тест генератора кадров"""
            def generate_test():
                try:
                    frame_count = 0
                    while self.stream_active:
                        try:
                            frame = self.frame_buffer.get(timeout=2.0)
                            frame_count += 1
                            yield f"data: Кадр {frame_count} получен, размер буфера: {self.frame_buffer.qsize()}\n\n"
                        except queue.Empty:
                            yield f"data: Буфер пуст (таймаут), активных потоков: {self.active_streams}\n\n"
                            time.sleep(0.1)
                        except Exception as e:
                            yield f"data: Ошибка: {str(e)}\n\n"
                            time.sleep(0.1)
                except Exception as e:
                    yield f"data: Генератор завершен: {str(e)}\n\n"
            
            return Response(generate_test(), mimetype='text/event-stream')

    def run(self):
        """Запуск сервера"""
        try:
            app_config = self.config['server']
            print(f"\n🚀 Запуск сервера на http://{app_config['host']}:{app_config['port']}")
            print("=" * 60)
            print("Нажмите Ctrl+C для остановки")
            print("=" * 60)
            
            self.app.run(
                host=app_config['host'],
                port=app_config['port'],
                debug=app_config['debug'],
                threaded=app_config['threaded']
            )
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Получен сигнал остановки...")
        except Exception as e:
            print(f"\n❌ Ошибка запуска сервера: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Очистка ресурсов"""
        print("\n🧹 Очистка ресурсов...")
        
        # Останавливаем стрим
        if hasattr(self, 'stream_active') and self.stream_active:
            self.stop_stream_internal()
        
        # Закрываем камеру
        if hasattr(self, 'camera_lock'):
            with self.camera_lock:
                if hasattr(self, 'current_camera') and self.current_camera:
                    try:
                        self.current_camera.release()
                        print("✅ Камера освобождена")
                    except Exception as e:
                        print(f"⚠️  Ошибка при освобождении камеры: {e}")
        
        print("👋 Сервер остановлен")

    def get_stream_state_info(self):
        """Получение информации о состоянии стрима для диагностики"""
        return {
            'stream_active': self.stream_active,
            'buffer_active': self.buffer_active,
            'frame_count': self.frame_count,
            'buffer_size': self.frame_buffer.qsize(),
            'buffer_maxsize': self.frame_buffer.maxsize,
            'camera_opened': self.current_camera.isOpened() if self.current_camera else False,
            'thread_alive': self.buffer_thread.is_alive() if self.buffer_thread else False,
            'thread_id': self.buffer_thread.ident if self.buffer_thread else None,
            'active_streams': self.active_streams,
            'active_clients': len(self.active_clients)
        }        


def log_all_available_cameras(logger):
    """Логировать все доступные камеры в файл лога"""
    try:
        print("🔍 Сканирование доступных камер...")
        
        # Создаем CameraChecker
        checker = CameraChecker(logger=logger)
        
        # Если у логгера есть метод для записи, используем его
        cameras = checker.detect_cameras(max_devices=10)
        
        if not cameras:
            if hasattr(logger, 'log_warning'):
                logger.log_warning("❌ Видеокамеры не найдены в системе")
            else:
                logger.info("❌ Видеокамеры не найдены в системе")
            return
        
        # Логируем через стандартный метод CameraChecker
        checker.log_detection_results_with_fps(cameras)
        
        # Также выводим в консоль для наглядности
        print(f"📊 Найдено камер: {len(cameras)}")
        for i, cam in enumerate(cameras, 1):
            name = checker._get_camera_name(cam['device_path'])
            formats = ', '.join(cam['formats'])
            print(f"{i}. {cam['device_path']} - {name}")
            print(f"   Форматы: {formats}")
        
        print("✅ Сканирование завершено")
        
    except Exception as e:
        print(f"⚠️  Ошибка при сканировании камер: {e}")
        # Пробуем записать ошибку в лог
        if hasattr(logger, 'log_error'):
            logger.log_error(f"Ошибка при сканировании камер: {e}")
        elif hasattr(logger, 'error'):
            logger.error(f"Ошибка при сканировании камер: {e}")
        else:
            logger.info(f"ОШИБКА: {e}")

def main():
    parser = argparse.ArgumentParser(description='Flask Webcam Stream with YAML Configuration')
    parser.add_argument('--config', '-c', default='config.yaml', 
                       help='Путь к конфигурационному файлу YAML (по умолчанию: config.yaml)')
    args = parser.parse_args()
    
    # Создаем логгер
    logger = create_logger(args.config)
    
    # Загружаем конфигурацию
    config = load_config(args.config)
    
    # Логируем информацию о запуске
    logger.log_startup_info(config)
    
    print("=" * 60)
    print("🔍 Поиск рабочей камеры...")
    print("=" * 60)
    
    camera = test_camera_backends(config, logger)
    
    if camera is None:
        logger.log_error("НЕ НАЙДЕНА РАБОЧАЯ КАМЕРА!")
        print("\n❌ НЕ НАЙДЕНА РАБОЧАЯ КАМЕРА!")
        sys.exit(1)
    
    print("\n✅ Камера найдена и готова к работе!")
    print(f"📁 Текущая директория: {os.getcwd()}")
    print(f"📁 Путь к скрипту: {os.path.dirname(os.path.abspath(__file__))}")
    print("=" * 60)

    # ✅ ДОБАВЛЯЕМ ЗДЕСЬ - логируем все доступные камеры
    print("\n📊 СКАНИРОВАНИЕ ВСЕХ ДОСТУПНЫХ КАМЕР:")
    print("=" * 60)          
    
    log_all_available_cameras(logger)  # ← Передаем логгер

    print("=" * 60) 
    
    # Создаем и запускаем стример
    try:
        streamer = CameraStreamer(config, logger, camera)

        # ✅ АВТОЗАПУСК СТРИМА ПРИ СТАРТЕ СЕРВЕРА
        if config.get('camera', {}).get('auto_start', False):
            print("🚀 Автозапуск стрима включен - запускаю...")
            logger.log_info("Автозапуск стрима включен в конфигурации")
            streamer.start_stream_internal()

        streamer.run()
    except Exception as e:
        print(f"❌ Ошибка создания CameraStreamer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()