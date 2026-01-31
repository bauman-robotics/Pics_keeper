#!/usr/bin/env python3
"""
Flask Web Server for Webcam Streaming - Version 4
YAML Configuration Support
"""

import yaml
import cv2
import sys
import threading
import time
import queue
import copy
from flask import Flask, Response, render_template, jsonify, request
import argparse
import os
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
                    
                    # Сохраняем информацию о найденной камере для логирования
                    camera_info = {
                        'name': name,
                        'resolution': resolution_str,
                        'fps': fps_str
                    }
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
        self.MAX_CONCURRENT_STREAMS = 2
        self.stream_lock = threading.Lock()
        
        # Инициализация Flask
        app_config = config['server']
        self.app = Flask(__name__, template_folder=config['paths']['templates_folder'])
        
        # Настройка маршрутов
        self.setup_routes()
        
        # Сканируем доступные камеры
        self.camera_checker = CameraChecker()
        self.available_cameras = self.camera_checker.detect_cameras()

    def get_client_info(self):
        """Получение информации о клиенте"""
        if hasattr(request, 'remote_addr'):
            user_ip = request.remote_addr
        else:
            user_ip = 'unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')
        return user_ip, user_agent        
    
    def get_fallback_image(self):
        """Возвращает статичное изображение при перегрузке"""
        import numpy as np
        
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
    
    def setup_routes(self):
        """Настройка маршрутов Flask"""
            
        @self.app.before_request
        def log_request():
            """Логирование всех запросов"""
            if request.endpoint and request.endpoint not in ['static', 'video_feed']:
                # Используем streamer_self вместо self
                user_ip, user_agent = streamer_self.get_client_info()
                
                streamer_self.logger.log_info(f"🌐 Запрос: {request.method} {request.path} | "
                                           f"IP: {user_ip} | "
                                           f"Endpoint: {request.endpoint}")
        
        @self.app.route('/')
        def index():
            """Главная страница с видео потоком"""
            user_ip, user_agent = streamer_self.get_client_info()
            streamer_self.logger.log_web_action('page_load', 'success', 'Main page loaded', user_ip, user_agent)
            return render_template('index.html')
        
        # ВАЖНО: video_feed должен быть декорирован как маршрут Flask
        @self.app.route('/video_feed')
        def video_feed():
            """Маршрут для видео потока с ограничением"""
            with self.stream_lock:
                if self.active_streams >= self.MAX_CONCURRENT_STREAMS:
                    print(f"⚠️  Превышено максимальное количество стримов: {self.active_streams}/{self.MAX_CONCURRENT_STREAMS}")
                    # Возвращаем статичное изображение вместо ошибки
                    return self.get_fallback_image()
                
                self.active_streams += 1
            
            print(f"📹 Клиент запросил video_feed (активных стримов: {self.active_streams})")
            
            def generate_with_cleanup():
                try:
                    for chunk in self.generate_from_buffer():
                        yield chunk
                except GeneratorExit:
                    print("📹 Клиент отключился (GeneratorExit)")
                except Exception as e:
                    print(f"📹 Ошибка в генераторе: {e}")
                finally:
                    with self.stream_lock:
                        self.active_streams = max(0, self.active_streams - 1)
                        print(f"📹 video_feed завершен (осталось стримов: {self.active_streams})")
            
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
            camera_list = []
            
            for cam in self.available_cameras:
                try:
                    # Безопасное получение данных
                    device_path = cam.get('device_path', 'unknown')
                    
                    # Форматы
                    formats = cam.get('formats', [])
                    
                    # Преобразуем resolutions_info в простой список разрешений
                    resolutions_info = cam.get('resolutions_info', {})
                    resolutions = []
                    
                    # Извлекаем все уникальные разрешения из resolutions_info
                    for fmt, res_dict in resolutions_info.items():
                        if isinstance(res_dict, dict):
                            for resolution in res_dict.keys():
                                if resolution not in resolutions:
                                    resolutions.append(resolution)
                    
                    # Получаем имя камеры с проверкой
                    camera_name = device_path  # значение по умолчанию
                    try:
                        if hasattr(self.camera_checker, '_get_camera_name'):
                            camera_name = self.camera_checker._get_camera_name(device_path)
                    except:
                        pass
                    
                    camera_info = {
                        'device_path': device_path,
                        'name': camera_name,
                        'formats': formats,
                        'resolutions': resolutions,
                        'is_current': device_path == self.config['camera']['device']
                    }
                    camera_list.append(camera_info)
                    
                except Exception as e:
                    print(f"⚠️  Ошибка обработки камеры: {e}")
                    continue
            
            return jsonify({
                'cameras': camera_list,
                'total': len(camera_list),
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
                
                was_streaming = self.stream_active
                
                # Останавливаем стрим если он активен
                if self.stream_active:
                    self.stop_stream_internal()
                
                # Закрываем текущую камеру с блокировкой
                with self.camera_lock:
                    if self.current_camera:
                        try:
                            self.current_camera.release()
                            print("📹 Закрыта старая камера")
                        except Exception as e:
                            print(f"⚠️  Ошибка при закрытии камеры: {e}")
                
                # Открываем новую камеру
                with self.camera_lock:
                    try:
                        new_camera = cv2.VideoCapture(device_path)
                        if new_camera.isOpened():
                            # Устанавливаем параметры
                            if 'width' in self.config['camera'] and 'height' in self.config['camera']:
                                new_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['camera']['width'])
                                new_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['camera']['height'])
                            
                            if 'fps' in self.config['camera']:
                                new_camera.set(cv2.CAP_PROP_FPS, self.config['camera']['fps'])
                            
                            # Обновляем конфигурацию
                            old_device = self.config['camera']['device']
                            self.config['camera']['device'] = device_path
                            
                            self.current_camera = new_camera
                            self.frame_count = 0
                            
                            print(f"📹 Камера изменена на {device_path}")
                            self.logger.log_web_action('select_camera', 'success', 
                                                    f'Camera changed from {old_device} to {device_path}',
                                                    user_ip, user_agent)
                            
                            # Автоматически перезапускаем стрим если он был активен
                            if was_streaming:
                                time.sleep(0.5)
                                threading.Thread(target=self.restart_stream_async, daemon=True).start()
                            
                            return jsonify({
                                'status': 'success', 
                                'message': f'Камера изменена на {device_path}',
                                'device_path': device_path,
                                'stream_restarting': was_streaming
                            })
                        else:
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
                        'frame_size': frame.shape if frame is not None else None
                    })
                else:
                    return jsonify({'status': 'error', 'message': 'Не удалось прочитать кадр'})

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
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Очистка ресурсов"""
        print("\n🧹 Очистка ресурсов...")
        
        # Останавливаем стрим
        if self.stream_active:
            self.stop_stream_internal()
        
        # Закрываем камеру
        with self.camera_lock:
            if self.current_camera:
                try:
                    self.current_camera.release()
                    print("✅ Камера освобождена")
                except Exception as e:
                    print(f"⚠️  Ошибка при освобождении камеры: {e}")
        
        print("👋 Сервер остановлен")

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
        print("\nПопробуйте:")
        print("  1. sudo apt install v4l-utils")
        print("  2. v4l2-ctl -d /dev/video0 --list-formats-ext")
        print("  3. cheese  (для теста камеры)")
        print("\nИли измените настройки камеры в конфигурационном файле")
        sys.exit(1)
    
    print("\n✅ Камера найдена и готова к работе!")
    print("=" * 60)
    
    # Создаем и запускаем стример
    streamer = CameraStreamer(config, logger, camera)
    streamer.run()

if __name__ == '__main__':
    main()