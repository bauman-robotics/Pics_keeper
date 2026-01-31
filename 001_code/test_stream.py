#!/usr/bin/env python3
"""
Тестовый скрипт для проверки MJPEG стрима

Этот скрипт запускает стрим и веб-сервер для тестирования.
"""

import sys
import os
import time
import argparse


# Добавляем путь к модулям
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def test_stream(args):
    """Тестирование стрима"""
    print("🧪 Тестирование MJPEG стрима")
    print("=" * 50)
    
    try:
        from config.cli_parser import parse_arguments
        from config.settings import ApplicationSettings
        from utils.logger import create_logger
        from core.stream_manager_universal import UniversalStreamManager, UniversalStreamConfig
        
        # Создаем простые настройки для теста
        settings = ApplicationSettings(
            camera={
                'camera_type': 'local_web',
                'resolution': 'stream',
                'exposure_time': 40000,
                'analogue_gain': 2.0,
                'ae_enable': False,
                'af_enable': False,
                'lens_position': 0.5
            },
            stream={
                'enabled': True,
                'width': 1280,
                'height': 720,
                'fps': 30,
                'quality': 50,
                'analysis': False,
                'low_latency': True,
                'port': args.port,
                'web_interface': not args.no_web
            },
            capture={
                'delay': 0,
                'count': 1,
                'output_dir': './003_pics',
                'jpeg_quality': 95,
                'max_angle': 45,
                'warn_angle': 30,
                'force_capture': False
            },
            preview={
                'enabled': False
            },
            debug={
                'enabled': True
            }
        )
        
        # Создаем логгер
        logger = create_logger('local_web')
        
        # Создаем конфигурацию для стрима
        stream_config = UniversalStreamConfig(
            camera_type='local_web',
            camera_index=0,
            target_width=args.width,
            target_height=args.height,
            max_fps=args.fps,
            show_fps=True,
            show_status=True,
            show_frame_info=False,
            low_latency=True,
            enable_visualization=True,
            enable_capture=True,
            capture_dir='./003_pics',
            file_prefix="test_stream",
            stream_port=args.port,
            web_interface=not args.no_web,
            stream_analysis=False,
            stream_quality=50
        )
        
        print("🎬 Создание менеджера стрима...")
        stream_manager = UniversalStreamManager(stream_config, logger)
        
        print("🚀 Запуск стрима...")
        if stream_manager.start():
            print("✅ Стрим запущен")
            
            print("🌐 Запуск веб-сервера...")
            if stream_manager.start_web_server():
                print("✅ Веб-сервер запущен")
                print(f"🌐 Откройте в браузере: http://localhost:{args.port}")
                print(f"🎬 Стрим доступен по: http://localhost:{args.port}/stream.mjpg")
                print(f"📸 Сделать снимок: http://localhost:{args.port}/capture")
                
                # Ждем несколько секунд для тестирования
                print("\n⏳ Стрим работает. Нажмите Ctrl+C для остановки...")
                print("💡 Проверьте:")
                print("   1. Откройте http://localhost:8080 в браузере")
                print("   2. Убедитесь, что видите видеопоток")
                print("   3. Проверьте FPS в правом верхнем углу")
                print("   4. Попробуйте сделать снимок через веб-интерфейс")
                
                try:
                    start_time = time.time()
                    frame_count = 0
                    
                    while stream_manager.is_running():
                        time.sleep(1)
                        frame_count += 1
                        
                        # Показываем статус каждые 5 секунд
                        if frame_count % 5 == 0:
                            status = stream_manager.get_status()
                            print(f"📊 Статус: {status.fps:.1f} FPS, {status.resolution[0]}x{status.resolution[1]}")
                        
                        # Автоматическая остановка через 10 секунд
                        if time.time() - start_time > 10:
                            print("\n⏱️  Автоматическая остановка через 10 секунд")
                            break
                            
                except KeyboardInterrupt:
                    print("\n🛑 Остановка по Ctrl+C...")
                
                print("\n🛑 Остановка стрима...")
                stream_manager.stop()
                stream_manager.stop_web_server()
                print("✅ Стрим остановлен")
                
            else:
                print("❌ Не удалось запустить веб-сервер")
                stream_manager.stop()
        else:
            print("❌ Не удалось запустить стрим")
            
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Тест MJPEG стрима')
    parser.add_argument('--camera', type=str, default='local_web', 
                       choices=['imx708', 'imx415', 'ov5647', 'local_web'],
                       help='Тип камеры')
    parser.add_argument('--width', type=int, default=1280, help='Ширина стрима')
    parser.add_argument('--height', type=int, default=720, help='Высота стрима')
    parser.add_argument('--fps', type=int, default=30, help='FPS стрима')
    parser.add_argument('--port', type=int, default=8081, help='Порт веб-сервера')
    parser.add_argument('--no-web', action='store_true', help='Отключить веб-интерфейс')
    
    args = parser.parse_args()
    
    print(f"🧪 Тест MJPEG стрима")
    print(f"📷 Камера: {args.camera}")
    print(f"🎬 Разрешение: {args.width}x{args.height} @ {args.fps} FPS")
    print(f"🌐 Порт: {args.port}")
    print(f"🌐 Веб-интерфейс: {'ВЫКЛ' if args.no_web else 'ВКЛ'}")
    print("=" * 50)
    
    test_stream(args)

if __name__ == "__main__":
    main()