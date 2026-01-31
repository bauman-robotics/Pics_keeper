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
from flask import Flask, Response, render_template, jsonify
import argparse
import os

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
    app = Flask(__name__, template_folder=config['paths']['templates_folder'])
    
    # Глобальные переменные для управления стримом
    stream_active = False
    stream_thread = None
    frame_count = 0
    
    def generate():
        """Генератор кадров для потоковой передачи"""
        nonlocal stream_active, frame_count
        print("🎬 Генератор кадров запущен")
        local_frame_count = 0
        error_count = 0
        stream_config = config['stream']
        
        while stream_active:
            success, frame = camera.read()
            
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
    
    @app.route('/')
    def index():
        """Главная страница с видео потоком"""
        return render_template('index.html')
    
    @app.route('/video_feed')
    def video_feed():
        """Маршрут для видео потока"""
        print("📹 Клиент запросил video_feed")
        return Response(generate(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/status')
    def status():
        """Страница статуса сервера"""
        return render_template('status.html')
    
    @app.route('/api/stream/start', methods=['POST'])
    def start_stream():
        """Запуск видеопотока"""
        nonlocal stream_active
        if not stream_active:
            stream_active = True
            print("🎬 Стрим запущен")
            return jsonify({'status': 'started', 'message': 'Видеопоток запущен'})
        else:
            return jsonify({'status': 'already_running', 'message': 'Видеопоток уже запущен'})
    
    @app.route('/api/stream/stop', methods=['POST'])
    def stop_stream():
        """Остановка видеопотока"""
        nonlocal stream_active
        if stream_active:
            stream_active = False
            print("🎬 Стрим остановлен")
            return jsonify({'status': 'stopped', 'message': 'Видеопоток остановлен'})
        else:
            return jsonify({'status': 'already_stopped', 'message': 'Видеопоток уже остановлен'})
    
    @app.route('/api/stream/status')
    def stream_status():
        """Получение статуса видеопотока"""
        nonlocal stream_active, frame_count
        return jsonify({
            'stream_active': stream_active,
            'frame_count': frame_count,
            'camera_connected': camera is not None and camera.isOpened(),
            'config': {
                'device': config['camera']['device'],
                'backend': config['camera']['backend'],
                'resolution': f"{config['camera'].get('width', 'auto')}x{config['camera'].get('height', 'auto')}",
                'fps': config['camera'].get('fps', 'auto'),
                'jpeg_quality': config['camera']['jpeg_quality']
            }
        })
    
    try:
        print(f"\n🚀 Запуск сервера на http://{app_config['host']}:{app_config['port']}")
        print("=" * 60)
        app.run(
            host=app_config['host'],
            port=app_config['port'],
            debug=app_config['debug'],
            threaded=app_config['threaded']
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Остановка...")
    finally:
        if camera:
            camera.release()
        print("✅ Камера освобождена")

if __name__ == '__main__':
    main()