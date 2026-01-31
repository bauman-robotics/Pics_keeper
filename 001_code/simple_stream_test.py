#!/usr/bin/env python3
"""
Простой тест для проверки MJPEG стрима
"""

import sys
import os
import time
import threading

# Добавляем путь к модулям
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def test_simple_stream():
    """Простой тест стрима"""
    print("🧪 Простой тест MJPEG стрима")
    print("=" * 50)
    
    try:
        from core.stream_server import StreamServer
        from utils.webcam_capture import WebcamCapture
        from utils.logger import create_logger
        
        # Создаем логгер
        logger = create_logger('test')
        
        # Проверяем веб-камеру
        print("📸 Проверка веб-камеры...")
        webcam = WebcamCapture('local_web', debug=True)
        if not webcam.initialize():
            print("❌ Веб-камера не доступна")
            return False
        
        print("✅ Веб-камера доступна")
        
        # Создаем веб-сервер
        print("🌐 Создание веб-сервера...")
        from core.stream_server import StreamServerConfig
        config = StreamServerConfig(
            port=8081,
            stream_width=1280,
            stream_height=720,
            stream_fps=30,
            stream_quality=50,
            stream_analysis=False,
            low_latency=True,
            camera_name="Test Camera",
            save_dir="./003_pics"
        )
        server = StreamServer(config, logger=logger)
        
        # Функция для получения кадров
        def get_frame():
            """Функция для получения кадров с веб-камеры"""
            try:
                frame = webcam.capture_frame()
                if frame is not None:
                    # Обновляем кадр в сервере
                    server.update_frame(frame)
                return frame
            except Exception as e:
                if server.debug_mode:
                    print(f"❌ Ошибка получения кадра: {e}")
                return None
        
        # Устанавливаем источник кадров
        server.set_frame_source(get_frame)
        
        # Запускаем сервер в отдельном потоке
        server_thread = threading.Thread(target=server.start_server, daemon=True)
        server_thread.start()
        
        # Ждем запуска сервера
        time.sleep(2)
        
        # Проверяем доступность сервера
        import requests
        try:
            response = requests.get('http://localhost:8081/', timeout=5)
            if response.status_code == 200:
                print("✅ Веб-сервер доступен")
                print(f"🌐 Страница загружена: {len(response.text)} байт")
            else:
                print(f"❌ Веб-сервер недоступен: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка проверки веб-сервера: {e}")
        
        # Проверяем стрим
        try:
            response = requests.get('http://localhost:8081/stream.mjpg', timeout=5, stream=True)
            if response.status_code == 200:
                print("✅ MJPEG стрим доступен")
                # Читаем немного данных из стрима
                data = b''
                for chunk in response.iter_content(chunk_size=1024):
                    data += chunk
                    if len(data) > 10000:  # Прочитать 10KB
                        break
                print(f"🎬 Получено данных из стрима: {len(data)} байт")
            else:
                print(f"❌ MJPEG стрим недоступен: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка проверки MJPEG стрима: {e}")
        
        # Останавливаем сервер
        print("🛑 Остановка сервера...")
        server.stop_server()
        server_thread.join(timeout=2)
        
        print("✅ Тест завершен")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_stream()