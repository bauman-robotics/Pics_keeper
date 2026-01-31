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
from flask import Flask, Response, render_template, jsonify, request
import argparse
import os
from utils.camera_checker import CameraChecker
from flask import send_from_directory

import queue
import copy

# Импортируем логгер
from utils.logger import create_logger

# Глобальные переменные для управления подключениями
active_streams = 0
MAX_CONCURRENT_STREAMS = 2  # Максимум 2 одновременных подключения


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


def main():
    parser = argparse.ArgumentParser(description='Flask Webcam Stream with YAML Configuration')
    parser.add_argument('--config', '-c', default='config.yaml', 
                       help='Путь к конфигурационному файлу YAML (по умолчанию: config.yaml)')
    args = parser.parse_args()
    
    # Создаем логгер
    logger = create_logger(args.config)
    
    # Загружаем конфигурацию
    config = load_config(args.config)
    
    # Сканируем доступные камеры
    available_cameras = logger.scan_available_cameras()


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
    
    # Инициализация Flask приложения
    app_config = config['server']
    app = Flask(__name__, 
        template_folder=config['paths']['templates_folder'],
        static_folder='static'  # Добавьте эту строку
    )
    
    # Глобальные переменные для управления стримом
    stream_active = False
    stream_thread = None
    frame_count = 0
    current_camera = camera
    current_camera_info = None

    # В начале функции main() после создания камеры:
    frame_buffer = queue.Queue(maxsize=30)  # Буфер на 30 кадров
    buffer_thread = None
    buffer_active = False
    last_frame = None
    frame_lock = threading.Lock()
    camera_lock = threading.Lock()
    
    # Сканируем доступные камеры для веб-интерфейса
    camera_checker = CameraChecker()
    available_cameras = camera_checker.detect_cameras()
        

def restart_stream_async():
    """Асинхронный перезапуск стрима"""
    time.sleep(1.0)
    # Имитируем POST запрос на start
    with app.test_client() as client:
        client.post('/api/stream/start')
    print("🔄 Стрим автоматически перезапущен после смены камеры")


def generate_from_buffer_with_heartbeat():
    """Генератор с heartbeat для поддержания соединения"""
    nonlocal stream_active
    
    print("🎬 Генератор кадров запущен (с heartbeat)")
    last_activity = time.time()
    
    for chunk in generate_from_buffer():
        yield chunk
        last_activity = time.time()
        
        # Отправляем heartbeat каждые 5 секунд
        if time.time() - last_activity > 5:
            # Пустой комментарий для поддержания соединения
            yield b'--frame\r\nContent-Type: text/plain\r\n\r\n\r\n'
                    
    def buffer_frames():
        """Фоновая задача для чтения кадров в буфер"""
        nonlocal buffer_active, current_camera, camera_lock, frame_buffer, last_frame, frame_lock
        
        print("📦 Запущен буферизатор кадров")
        error_count = 0
        
        while buffer_active:
            with camera_lock:
                if current_camera is None or not current_camera.isOpened():
                    print("❌ Камера не доступна в буфере")
                    time.sleep(0.1)
                    continue
                
                success, frame = current_camera.read()
            
            if success and frame is not None:
                error_count = 0  # Сброс счетчика ошибок
                
                # Сохраняем последний кадр
                with frame_lock:
                    last_frame = frame.copy()
                
                # Добавляем в буфер если есть место
                if not frame_buffer.full():
                    try:
                        # Копируем кадр для безопасности
                        frame_buffer.put_nowait(frame.copy())
                    except queue.Full:
                        pass
                else:
                    # Если буфер полон, заменяем самый старый кадр
                    try:
                        frame_buffer.get_nowait()  # Удаляем старый
                        frame_buffer.put_nowait(frame.copy())  # Добавляем новый
                    except (queue.Empty, queue.Full):
                        pass
            else:
                error_count += 1
                print(f"📦 Ошибка чтения кадра в буфере, попытка {error_count}")
                
                if error_count > 5:
                    print("📦 Слишком много ошибок в буфере")
                    # Используем последний сохраненный кадр
                    with frame_lock:
                        if last_frame is not None and not frame_buffer.full():
                            try:
                                frame_buffer.put_nowait(last_frame.copy())
                            except queue.Full:
                                pass
            
            # Контроль FPS
            target_fps = config['camera'].get('fps', 30)
            if target_fps > 0:
                time.sleep(1.0 / target_fps)
            else:
                time.sleep(0.033)  # 30 FPS по умолчанию
        
        print("📦 Остановлен буферизатор кадров")

    def generate_from_buffer():
        """Генератор кадров из буфера"""
        nonlocal stream_active, frame_count
        
        print("🎬 Генератор кадров запущен (из буфера)")
        local_frame_count = 0
        error_count = 0
        empty_buffer_count = 0
        
        while stream_active:
            try:
                # Пытаемся получить кадр из буфера
                frame = frame_buffer.get(timeout=0.5)
                
                error_count = 0
                empty_buffer_count = 0
                
                local_frame_count += 1
                frame_count += 1
                
                if local_frame_count % 30 == 0:
                    print(f"📊 Отправлено кадров: {local_frame_count} (буфер: {frame_buffer.qsize()}/30)")
                
                # Кодируем кадр
                ret, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 
                    config['camera'].get('jpeg_quality', 85)
                ])
                
                if not ret:
                    print("⚠️ Ошибка кодирования JPEG")
                    continue
                
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
            except queue.Empty:
                empty_buffer_count += 1
                error_count += 1
                
                if empty_buffer_count > 3:
                    print(f"⚠️ Буфер пуст, попытка {empty_buffer_count}")
                
                # Если буфер пуст, используем последний сохраненный кадр
                if error_count > 2:
                    with frame_lock:
                        if last_frame is not None:
                            try:
                                ret, buffer = cv2.imencode('.jpg', last_frame, [
                                    cv2.IMWRITE_JPEG_QUALITY, 
                                    config['camera'].get('jpeg_quality', 85)
                                ])
                                
                                if ret:
                                    frame_bytes = buffer.tobytes()
                                    yield (b'--frame\r\n'
                                        b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                                    continue
                            except Exception as e:
                                print(f"⚠️ Ошибка при использовании последнего кадра: {e}")
                
                if error_count > 10:
                    print("💥 Слишком много ошибок, останавливаем стрим")
                    break
                
                # Пауза перед следующей попыткой
                time.sleep(0.1)
        
        print("🎬 Генератор кадров остановлен")

    def get_client_info():
        """Получение информации о клиенте"""
        user_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        return user_ip, user_agent

    def generate():
        """Генератор кадров для потоковой передачи"""
        nonlocal stream_active, frame_count, current_camera, camera_lock  # <-- добавили camera_lock
        
        print("🎬 Генератор кадров запущен")
        local_frame_count = 0
        error_count = 0
        stream_config = config['stream']
        
        while stream_active:
            # Используем блокировку для безопасного доступа к камере
            with camera_lock:
                if current_camera is None or not current_camera.isOpened():
                    print("❌ Камера не открыта")
                    break
                success, frame = current_camera.read()
            
            if not success or frame is None:
                error_count += 1
                print(f"❌ Ошибка чтения кадра #{local_frame_count}, попытка {error_count}")
                
                if error_count > stream_config['max_error_count']:
                    print("💥 Слишком много ошибок, останавливаем стрим")
                    break
                continue
            
            error_count = 0  # Сброс счетчика ошибок
            local_frame_count += 1
            frame_count += 1
            
            if local_frame_count % stream_config['frame_log_interval'] == 0:
                print(f"📊 Отправлено кадров: {local_frame_count}")
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config['camera']['jpeg_quality']])
            if not ret:
                print("⚠️ Ошибка кодирования JPEG")
                continue
            
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        print("🎬 Генератор кадров остановлен")

    @app.before_request
    def log_request():
        """Логирование всех запросов"""
        if request.endpoint and request.endpoint not in ['static', 'video_feed']:
            user_ip, user_agent = get_client_info()
            
            logger.log_info(f"🌐 Запрос: {request.method} {request.path} | "
                        f"IP: {user_ip} | "
                        f"Endpoint: {request.endpoint}")

    @app.route('/')
    def index():
        """Главная страница с видео потоком"""
        user_ip, user_agent = get_client_info()
        logger.log_web_action('page_load', 'success', 'Main page loaded', user_ip, user_agent)
        return render_template('index.html')
    
    @app.route('/video_feed')
    def video_feed():
        """Маршрут для видео потока с ограничением"""
        nonlocal active_streams
        
        with stream_lock:
            if active_streams >= MAX_CONCURRENT_STREAMS:
                print(f"⚠️  Превышено максимальное количество стримов: {active_streams}/{MAX_CONCURRENT_STREAMS}")
                # Возвращаем последний кадр вместо ошибки
                with frame_lock:
                    if last_frame is not None:
                        ret, buffer = cv2.imencode('.jpg', last_frame, [
                            cv2.IMWRITE_JPEG_QUALITY, 
                            config['camera'].get('jpeg_quality', 85)
                        ])
                        if ret:
                            frame_bytes = buffer.tobytes()
                            return Response(
                                b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n',
                                mimetype='multipart/x-mixed-replace; boundary=frame'
                            )
                return Response("Too many streams", status=429)
            
            active_streams += 1
        
        print(f"📹 Клиент запросил video_feed (активных стримов: {active_streams})")
        
        def generate_with_cleanup():
            try:
                for chunk in generate_from_buffer():
                    yield chunk
            except GeneratorExit:
                print("📹 Клиент отключился")
            except Exception as e:
                print(f"📹 Ошибка в генераторе: {e}")
            finally:
                with stream_lock:
                    nonlocal active_streams
                    active_streams = max(0, active_streams - 1)
                    print(f"📹 video_feed завершен (осталось стримов: {active_streams})")
        
        return Response(generate_with_cleanup(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
        
    @app.route('/status')
    def status():
        """Страница статуса сервера"""
        user_ip, user_agent = get_client_info()
        logger.log_web_action('page_load', 'success', 'Status page loaded', user_ip, user_agent)
        return render_template('status.html')
        
    @app.route('/api/stream/start', methods=['POST'])
    def start_stream():
        """Запуск видеопотока"""
        nonlocal stream_active, buffer_active, buffer_thread, frame_count, frame_buffer
        
        user_ip, user_agent = get_client_info()
        
        if not stream_active:
            # Проверяем камеру
            if current_camera is None or not current_camera.isOpened():
                logger.log_web_action('start_stream', 'error', 'Camera not ready', user_ip, user_agent)
                return jsonify({'status': 'error', 'message': 'Камера не готова'})
            
            # Очищаем буфер
            while not frame_buffer.empty():
                try:
                    frame_buffer.get_nowait()
                except queue.Empty:
                    break
            
            # Запускаем буферизатор
            buffer_active = True
            buffer_thread = threading.Thread(target=buffer_frames, daemon=True)
            buffer_thread.start()
            
            # Даем время на заполнение буфера
            time.sleep(0.5)
            
            # Запускаем стрим
            stream_active = True
            frame_count = 0
            
            print("🎬 Стрим запущен (с буферизацией)")
            logger.log_web_action('start_stream', 'success', 
                                f"Stream started on {config['camera']['device']}",
                                user_ip, user_agent)
            logger.log_button_click('start_stream', 'index', user_ip)
            return jsonify({'status': 'started', 'message': 'Видеопоток запущен'})
        else:
            logger.log_web_action('start_stream', 'warning', 'Stream already running',
                                user_ip, user_agent)
            return jsonify({'status': 'already_running', 'message': 'Видеопоток уже запущен'})

    @app.route('/api/stream/stop', methods=['POST'])
    def stop_stream():
        """Остановка видеопотока"""
        nonlocal stream_active, buffer_active, frame_buffer
        
        user_ip, user_agent = get_client_info()
        
        if stream_active:
            # Останавливаем стрим
            stream_active = False
            
            # Даем время на остановку генератора
            time.sleep(0.5)
            
            # Останавливаем буферизатор
            buffer_active = False
            
            # Даем время на остановку буферизатора
            time.sleep(0.5)
            
            # Очищаем буфер
            while not frame_buffer.empty():
                try:
                    frame_buffer.get_nowait()
                except queue.Empty:
                    break
            
            print("🎬 Стрим остановлен")
            logger.log_web_action('stop_stream', 'success', 
                                f"Stream stopped on {config['camera']['device']}",
                                user_ip, user_agent)
            logger.log_button_click('stop_stream', 'index', user_ip)
            return jsonify({'status': 'stopped', 'message': 'Видеопоток остановлен'})
        else:
            logger.log_web_action('stop_stream', 'warning', 'Stream already stopped',
                                user_ip, user_agent)
            return jsonify({'status': 'already_stopped', 'message': 'Видеопоток уже остановлен'})
        
    @app.route('/api/stream/status')
    def stream_status():
        """Получение статуса видеопотока"""
        nonlocal stream_active, frame_count, current_camera, camera_lock
        
        # Проверяем состояние камеры с блокировкой
        camera_ready = False
        with camera_lock:
            if current_camera:
                try:
                    camera_ready = current_camera.isOpened()
                except:
                    camera_ready = False
        
        return jsonify({
            'stream_active': stream_active,
            'frame_count': frame_count,
            'camera_ready': camera_ready,
            'camera_device': config['camera']['device'],
            'config': {
                'device': config['camera']['device'],
                'backend': config['camera']['backend'],
                'resolution': f"{config['camera'].get('width', 'auto')}x{config['camera'].get('height', 'auto')}",
                'fps': config['camera'].get('fps', 'auto'),
                'jpeg_quality': config['camera']['jpeg_quality']
            }
        })
    
    @app.route('/api/cameras')
    def get_cameras():
        """Получение списка доступных камер"""
        camera_list = []
        
        for cam in available_cameras:
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
                    if hasattr(camera_checker, '_get_camera_name'):
                        camera_name = camera_checker._get_camera_name(device_path)
                except:
                    pass
                
                camera_info = {
                    'device_path': device_path,
                    'name': camera_name,
                    'formats': formats,
                    'resolutions': resolutions,
                    'is_current': device_path == config['camera']['device']
                }
                camera_list.append(camera_info)
                
            except Exception as e:
                print(f"⚠️  Ошибка обработки камеры: {e}")
                continue
        
        return jsonify({
            'cameras': camera_list,
            'total': len(camera_list),
            'current_device': config['camera']['device']
        })


    @app.route('/api/cameras/select', methods=['POST'])
    def select_camera():
        """Выбор камеры для стрима"""
        nonlocal current_camera, stream_active, buffer_active, frame_count, camera_lock, frame_buffer
        
        user_ip, user_agent = get_client_info()
        
        try:
            device_path = request.json.get('device_path')
            if not device_path:
                logger.log_web_action('select_camera', 'error', 'No device path specified',
                                    user_ip, user_agent)
                return jsonify({'status': 'error', 'message': 'Не указан путь к устройству'})
            
            was_streaming = stream_active
            
            # Останавливаем стрим если он активен
            if stream_active:
                stream_active = False
                buffer_active = False
                time.sleep(1.0)  # Даем время на полную остановку
            
            # Очищаем буфер
            while not frame_buffer.empty():
                try:
                    frame_buffer.get_nowait()
                except queue.Empty:
                    break
            
            # Закрываем текущую камеру с блокировкой
            with camera_lock:
                if current_camera:
                    try:
                        current_camera.release()
                        print("📹 Закрыта старая камера")
                    except Exception as e:
                        print(f"⚠️  Ошибка при закрытии камеры: {e}")
            
            # Открываем новую камеру
            with camera_lock:
                try:
                    new_camera = cv2.VideoCapture(device_path)
                    if new_camera.isOpened():
                        # Устанавливаем параметры
                        if 'width' in config['camera'] and 'height' in config['camera']:
                            new_camera.set(cv2.CAP_PROP_FRAME_WIDTH, config['camera']['width'])
                            new_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config['camera']['height'])
                        
                        if 'fps' in config['camera']:
                            new_camera.set(cv2.CAP_PROP_FPS, config['camera']['fps'])
                        
                        # Обновляем конфигурацию
                        old_device = config['camera']['device']
                        config['camera']['device'] = device_path
                        
                        current_camera = new_camera
                        frame_count = 0
                        
                        print(f"📹 Камера изменена на {device_path}")
                        logger.log_web_action('select_camera', 'success', 
                                            f'Camera changed from {old_device} to {device_path}',
                                            user_ip, user_agent)
                        
                        # Автоматически перезапускаем стрим если он был активен
                        if was_streaming:
                            time.sleep(0.5)
                            # Запускаем асинхронно, чтобы не блокировать ответ
                            threading.Thread(target=restart_stream_async, daemon=True).start()
                        
                        return jsonify({
                            'status': 'success', 
                            'message': f'Камера изменена на {device_path}',
                            'device_path': device_path,
                            'stream_restarting': was_streaming
                        })
                    else:
                        logger.log_web_action('select_camera', 'error', 
                                            f'Failed to open camera {device_path}',
                                            user_ip, user_agent)
                        return jsonify({'status': 'error', 'message': 'Не удалось открыть камеру'})
                except Exception as e:
                    logger.log_web_action('select_camera', 'error', 
                                        f'Exception during camera switch: {str(e)}',
                                        user_ip, user_agent)
                    return jsonify({'status': 'error', 'message': f'Ошибка при переключении камеры: {str(e)}'})
                    
        except Exception as e:
            logger.log_web_action('select_camera', 'error', f'Unexpected error: {str(e)}',
                                user_ip, user_agent)
            return jsonify({'status': 'error', 'message': f'Неожиданная ошибка: {str(e)}'})
        


    @app.route('/settings')
    def settings_page():
        """Страница настроек"""
        user_ip, user_agent = get_client_info()
        logger.log_web_action('page_load', 'success', 'Settings page loaded', user_ip, user_agent)
        return render_template('settings.html')

    @app.route('/api/settings/save', methods=['POST'])
    def save_settings():
        """Сохранение настроек"""
        user_ip, user_agent = get_client_info()
        
        try:
            settings = request.json
            if not settings:
                logger.log_web_action('save_settings', 'error', 'No settings provided',
                                    user_ip, user_agent)
                return jsonify({'status': 'error', 'message': 'Настройки не предоставлены'})
            
            logger.log_button_click('save_settings', 'settings', user_ip, settings)
            
            # Здесь логика сохранения настроек
            # ...
            
            logger.log_web_action('save_settings', 'success', 
                                f'Settings saved: {settings}', user_ip, user_agent)
            return jsonify({'status': 'success', 'message': 'Настройки сохранены'})
            
        except Exception as e:
            logger.log_web_action('save_settings', 'error', f'Error saving settings: {str(e)}',
                                user_ip, user_agent)
            return jsonify({'status': 'error', 'message': f'Ошибка сохранения настроек: {str(e)}'})        

    @app.route('/api/logs')
    def get_logs():
        """Получение логов"""
        try:
            log_file = logger.get_log_file_path()
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # Последние 100 строк
            
            logs = []
            for line in lines:
                log_entry = {'message': line.strip()}
                
                if 'ERROR' in line:
                    log_entry['type'] = 'error'
                elif 'WARNING' in line:
                    log_entry['type'] = 'warning'
                elif 'Нажатие кнопки' in line:
                    log_entry['type'] = 'button-click'
                elif 'Веб-действие' in line:
                    log_entry['type'] = 'web-action'
                else:
                    log_entry['type'] = 'info'
                
                logs.append(log_entry)
            
            return jsonify({'logs': logs})
        except Exception as e:
            return jsonify({'logs': [], 'error': str(e)})

    @app.route('/logs')
    def logs_page():
        """Страница с логами"""
        user_ip, user_agent = get_client_info()
        logger.log_web_action('page_load', 'success', 'Logs page loaded', user_ip, user_agent)
        return render_template('logs.html')


    try:
        print(f"\n🚀 Запуск сервера на http://{app_config['host']}:{app_config['port']}")
        print("=" * 60)
        print("Нажмите Ctrl+C для остановки")
        print("=" * 60)
        
        app.run(
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
        if current_camera:
            try:
                current_camera.release()
                print("✅ Камера освобождена")
            except Exception as e:
                print(f"⚠️  Ошибка при освобождении камеры: {e}")
        print("👋 Сервер остановлен")

    @app.route('/api/camera/test', methods=['GET'])
    def test_camera():
        """Тест камеры - попытка чтения кадра"""
        nonlocal current_camera
        
        try:
            if current_camera is None:
                return jsonify({'status': 'error', 'message': 'Камера не инициализирована'})
            
            if not current_camera.isOpened():
                return jsonify({'status': 'error', 'message': 'Камера не открыта'})
            
            success, frame = current_camera.read()
            if success and frame is not None:
                # Пробуем получить параметры камеры
                width = int(current_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(current_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(current_camera.get(cv2.CAP_PROP_FPS))
                
                return jsonify({
                    'status': 'success',
                    'message': 'Камера работает',
                    'resolution': f'{width}x{height}',
                    'fps': fps,
                    'frame_size': frame.shape if frame is not None else None
                })
            else:
                return jsonify({'status': 'error', 'message': 'Не удалось прочитать кадр'})
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка: {str(e)}'})


    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)

if __name__ == '__main__':
    main()