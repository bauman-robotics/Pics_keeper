#!/usr/bin/env python3
"""
Точка входа в приложение Pics_keeper


file_name: main.py 
old_name:  01_pics_keeper.py
old_name: /home/pi/projects/Hailo8_projects/cam_calibr/49_get_calbr_data_full_size_Ok.py

rpicam-still --list-cameras

python3 001_code/main.py --debug --stream-fps 25 --no-analysis --delay 3
python3 001_code/main.py 
# ======
export DISPLAY=:0

1. убить сессию:
screen -X -S bird_detector quit

2. активация вирт окружения
source venv/bin/activate

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

"""

import sys
import os

def main():
    """Основная функция приложения"""
    # Определяем базовую директорию (где находится main.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    
    # Добавляем базовую директорию в sys.path для корректного импорта
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    
    # Импортируем модули для проверки их загрузки
    try:
        from config.camera_profiles import get_camera_profile, get_default_settings
        from config.settings import ApplicationSettings
        from config.cli_parser import parse_arguments
        from utils.logger import create_logger
        
        print("✅ Модули успешно загружены")
        
    except ImportError as e:
        print(f"❌ Ошибка загрузки модулей: {e}")
        sys.exit(1)
    
    # Парсим аргументы командной строки
    settings = parse_arguments()
    
    # Выбираем модуль захвата в зависимости от типа камеры
    if settings.camera.camera_type == 'local_web':
        # Для веб-камеры используем ffmpeg
        try:
            from utils.webcam_capture import capture_photo_by_keypress
            print("✅ Используется веб-камера")
        except ImportError:
            print("❌ Модуль веб-камеры не доступен")
            sys.exit(1)
    else:
        # Для настоящих камер пытаемся использовать picamera2
        try:
            from utils.camera_capture import capture_photo_by_keypress
            print("✅ Используется реальная камера")
        except ImportError:
            # Если нет picamera2, используем заглушку
            from utils.camera_capture_mock import capture_photo_by_keypress
            print("✅ Используется заглушка камеры")
    
    # Создаем логгер
    logger = create_logger(settings.camera.camera_type)
    
    # Логируем аргументы командной строки с настройками
    logger.log_arguments(settings, settings)
    
    # Логируем информацию о путях
    logger.log_paths_info(settings)
    
    # Выводим информацию о настройках
    print("🚀 Pics_keeper - модульная архитектура")
    print(f"📷 Камера: {settings.camera.camera_type}")
    print(f"🎬 Стрим: {'ВКЛ' if settings.stream.enabled else 'ВЫКЛ'} ({settings.stream.width}x{settings.stream.height} @ {settings.stream.fps} FPS)")
    print(f"📸 Съемка: {settings.capture.count} фото в {settings.capture.output_dir}")
    print(f"🔧 Отладка: {'ВКЛ' if settings.debug.enabled else 'ВЫКЛ'}")
    print(f"🎯 Контроль углов: {settings.capture.max_angle}° макс.")
    print(f"📁 Лог-файл: {logger.get_log_file_path()}")
    
    # Запускаем съемку по нажатию клавиши
    print("\n📸 Запуск съемки фото по нажатию клавиши...")
    print(f"📁 Сохранение в: {settings.capture.output_dir}")
    
    success = capture_photo_by_keypress(
        camera_type=settings.camera.camera_type,
        resolution=settings.camera.resolution,
        delay=settings.capture.delay,
        save_dir=settings.capture.output_dir,
        jpeg_quality=settings.capture.jpeg_quality,
        debug=settings.debug.enabled
    )
    
    if success:
        print("\n✅ Съемка завершена успешно!")
    else:
        print("\n❌ Съемка завершена с ошибками!")
    
    print("\n✅ Этап 1 завершен: инфраструктура подготовлена, модули загружены")

if __name__ == "__main__":
    main()
