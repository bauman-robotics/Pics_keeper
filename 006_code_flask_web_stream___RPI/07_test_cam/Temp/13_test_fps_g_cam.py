#!/usr/bin/env python3
"""
Скрипт для тестового захвата видео в разных разрешениях
Без предпросмотра, только запись для последующего анализа
"""

import cv2
import time
import os
import subprocess
import sys
from datetime import datetime

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
# Раскомментируйте следующую строку, чтобы всегда запускать в режиме --default
# RUN_DEFAULT = True

# Или оставьте закомментированной для интерактивного режима
RUN_DEFAULT = True # False  # Измените на True для автоматического режима

# ============================================================
# ПАРАМЕТРЫ РЕЖИМА DEFAULT
# ============================================================
DEFAULT_BACKEND = 'MJPEG'    # 'MJPEG' или 'YUYV'
DEFAULT_WIDTH = 1920          # ширина кадра
DEFAULT_HEIGHT = 1200         # высота кадра
DEFAULT_FPS = 90             # целевой FPS
DEFAULT_DURATION = 10        # длительность записи в секундах

# ============================================================
# МАКРОСЫ ДЛЯ ОПТИМИЗАЦИИ
# ============================================================

# Режим "только статистика" - без сохранения видео
# Если True: не сохраняет видео, только собирает статистику
# Если False: сохраняет видео (как обычно)
STATS_ONLY_MODE = True # False  # Измените на True для режима только статистики

# Дополнительные макросы для тонкой настройки
SAVE_EVERY_NTH_FRAME = 1  # Сохранять каждый N-й кадр (1 = все)
MAX_FRAMES_IN_RAM = 1000   # Максимальное количество кадров в RAM (для статистики)
USE_LIGHTWEIGHT_STATS = False  # Использовать облегченную статистику (без хранения кадров)


# Режимы для полного тестирования (используются в run_all_tests)
TEST_MODES = [
    # MJPEG режимы (сжатые)
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90, 'name': 'Max resolution @ 90fps'},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60, 'name': 'Max resolution @ 60fps'},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30, 'name': 'Max resolution @ 30fps'},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90, 'name': '720p @ 90fps'},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 60, 'name': '720p @ 60fps'},
    {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90, 'name': 'VGA @ 90fps'},
    
    # YUYV режимы (несжатые)
    {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5, 'name': 'Max YUYV @ 5fps'},
    {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10, 'name': '720p YUYV @ 10fps'},
    {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30, 'name': 'VGA YUYV @ 30fps'},
    {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90, 'name': 'QVGA YUYV @ 90fps'},
]

# Режимы для MJPEG-only тестирования
MJPEG_ONLY_MODES = [
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60},
    {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30},
    {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90},
    {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90},
]

# Режимы для YUYV-only тестирования
YUYV_ONLY_MODES = [
    {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5},
    {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10},
    {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30},
    {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90},
]

# ============================================================
# ОСНОВНОЙ КОД
# ============================================================

class Logger:
    """Класс для логирования в файл и на экран"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.log_file = None
        self.terminal = sys.stdout
        
        # Создаем директорию для логов если её нет
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    def start_logging(self, test_name):
        """Начать логирование в файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_test_name = test_name.replace(" ", "_").replace("@", "").replace("|", "-")
        log_filename = f"{self.log_dir}/{timestamp}_{safe_test_name}.log"
        
        self.log_file = open(log_filename, 'w', encoding='utf-8')
        print(f"📝 Лог сохраняется в: {log_filename}")
        return log_filename
    
    def write(self, message):
        """Записать сообщение и в терминал, и в лог-файл"""
        # В терминал
        self.terminal.write(message)
        self.terminal.flush()
        
        # В лог-файл
        if self.log_file:
            self.log_file.write(message)
            self.log_file.flush()
    
    def flush(self):
        """Flush метод для совместимости"""
        self.terminal.flush()
        if self.log_file:
            self.log_file.flush()
    
    def stop_logging(self):
        """Остановить логирование в файл"""
        if self.log_file:
            self.log_file.close()
            self.log_file = None

class VideoCaptureTester:
    def __init__(self, device_id=8, output_dir="test_videos", log_dir="logs"):
        """
        Инициализация тестера
        
        Args:
            device_id: ID видеоустройства (/dev/video{device_id})
            output_dir: директория для сохранения видео
            log_dir: директория для сохранения логов
        """
        self.device_id = device_id
        self.output_dir = output_dir
        self.log_dir = log_dir
        self.logger = Logger(log_dir)
        
        # Создаем директорию для видео если её нет
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Создана директория: {output_dir}")
    
    def get_camera_info(self):
        """Получение информации о камере"""
        info = "\n" + "="*80 + "\n"
        info += "🔍 ИНФОРМАЦИЯ О КАМЕРЕ\n"
        info += "="*80 + "\n"
        
        print(info, end='')
        
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
    
    def test_resolution(self, backend, width, height, target_fps, duration=10):
        """
        Тестирование с поддержкой режима только статистики
        """
        # Создаем имя теста для лога
        mode_str = "STATS_ONLY" if STATS_ONLY_MODE else "FULL_CAPTURE"
        test_name = f"{mode_str}_{backend}_{width}x{height}_{target_fps}fps"
        
        # Начинаем логирование
        log_file = self.logger.start_logging(test_name)
        
        # Перенаправляем stdout в логгер
        old_stdout = sys.stdout
        sys.stdout = self.logger
        
        try:
            print(f"\n{'#'*80}")
            mode_info = "📊 РЕЖИМ ТОЛЬКО СТАТИСТИКА (без сохранения)" if STATS_ONLY_MODE else "🎥 ПОЛНЫЙ РЕЖИМ (с сохранением)"
            print(f"{mode_info}")
            print(f"🎥 ТЕСТ: {backend} | {width}x{height} | {target_fps} fps | {duration} сек")
            print(f"{'#'*80}")
            print(f"📝 Лог файл: {log_file}")
            
            # Формируем имя файла (только если не STATS_ONLY)
            filename = None
            if not STATS_ONLY_MODE:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if backend.upper() == 'MJPEG':
                    ext = 'avi'
                    fourcc_code = cv2.VideoWriter_fourcc(*'MJPG')
                else:
                    ext = 'avi'
                    fourcc_code = cv2.VideoWriter_fourcc(*'FFV1')
                filename = f"{self.output_dir}/{backend}_{width}x{height}_{target_fps}fps_{timestamp}.{ext}"
            
            # Открываем камеру
            cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)
            
            # Устанавливаем параметры
            if backend.upper() == 'MJPEG':
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            else:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, target_fps)
            
            time.sleep(1)
            
            # Проверяем реальные параметры
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps_set = cap.get(cv2.CAP_PROP_FPS)
            
            print(f"\n📊 Реальные параметры:")
            print(f"  Размер: {actual_width}x{actual_height}")
            print(f"  Установленный FPS: {actual_fps_set:.1f}")
            print(f"  Режим: {'Только статистика' if STATS_ONLY_MODE else 'Полный захват'}")
            
            if actual_width != width or actual_height != height:
                print(f"❌ Размер {width}x{height} не поддерживается")
                cap.release()
                return False
            
            # Статистика
            frame_count = 0
            start_time = time.time()
            fps_log = []
            last_log_time = start_time
            bytes_processed = 0  # Считаем обработанные данные
            
            # Для режима с сохранением - храним кадры
            frames = [] if not STATS_ONLY_MODE else None
            
            print(f"\n⏱️  Захват {duration} секунд...")
            
            try:
                while time.time() - start_time < duration:
                    ret, frame = cap.read()
                    
                    if ret:
                        frame_count += 1
                        
                        if STATS_ONLY_MODE:
                            # В режиме статистики только считаем байты
                            bytes_processed += frame.nbytes
                        else:
                            # В полном режиме сохраняем кадры
                            if frame_count % SAVE_EVERY_NTH_FRAME == 0:
                                if len(frames) < MAX_FRAMES_IN_RAM:
                                    frames.append(frame.copy())
                                bytes_processed += frame.nbytes
                        
                        # Логируем каждые 2 секунды
                        current_time = time.time()
                        if current_time - last_log_time >= 2.0:
                            elapsed = current_time - start_time
                            current_fps = frame_count / elapsed
                            fps_log.append(current_fps)
                            
                            # Плотность потока в МБ/сек
                            mb_per_sec = (bytes_processed / (1024 * 1024)) / elapsed
                            
                            # Индикатор режима
                            mode_indicator = "📊" if STATS_ONLY_MODE else "💾"
                            print(f"  {mode_indicator} Секунда {int(elapsed)}: {current_fps:.2f} fps | {mb_per_sec:.2f} МБ/с | кадров: {frame_count}")
                            
                            if not STATS_ONLY_MODE:
                                mem_usage = len(frames) * frame.nbytes / (1024 * 1024)
                                print(f"     RAM: {mem_usage:.1f} MB / {MAX_FRAMES_IN_RAM * frame.nbytes / (1024 * 1024):.1f} MB max")
                            
                            last_log_time = current_time
                    else:
                        print("⚠️  Пропуск кадра")
                        time.sleep(0.001)
                        
            except KeyboardInterrupt:
                print("\n⏹️  Запись прервана пользователем")
            
            finally:
                total_time = time.time() - start_time
                actual_fps = frame_count / total_time if total_time > 0 else 0
                
                # В полном режиме - сохраняем видео
                if not STATS_ONLY_MODE and frames and filename:
                    print(f"\n📝 Создание видеофайла с FPS = {actual_fps:.2f}...")
                    
                    writer = cv2.VideoWriter(filename, fourcc_code, actual_fps, (actual_width, actual_height))
                    
                    if writer.isOpened():
                        for i, frame in enumerate(frames):
                            writer.write(frame)
                            if (i + 1) % 50 == 0:
                                print(f"  Записано: {i + 1}/{len(frames)}")
                        writer.release()
                        print(f"✅ Видео: {filename}")
                        
                        # Проверка ffprobe
                        try:
                            result = subprocess.run(
                                ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                                '-show_entries', 'stream=r_frame_rate,nb_frames', 
                                '-show_entries', 'format=duration', filename],
                                capture_output=True, text=True
                            )
                            print(f"\n🔍 ffprobe: {result.stdout}")
                        except: pass
                    else:
                        print("❌ Ошибка создания видео")
                
                cap.release()
                
                # Итоговая статистика
                mb_per_sec = (bytes_processed / (1024 * 1024)) / total_time if total_time > 0 else 0
                
                print(f"\n📊 ИТОГИ ТЕСТА:")
                print(f"  Режим: {'Только статистика' if STATS_ONLY_MODE else 'Полный'}")
                print(f"  Всего кадров: {frame_count}")
                print(f"  Время: {total_time:.2f} сек")
                print(f"  Средний FPS: {actual_fps:.2f}")
                print(f"  Целевой FPS: {target_fps}")
                print(f"  Эффективность: {(actual_fps/target_fps)*100:.1f}%")
                print(f"  Плотность потока: {mb_per_sec:.2f} МБ/сек")
                print(f"  Всего данных: {bytes_processed/(1024*1024):.2f} MB")
                
                if fps_log:
                    print(f"  Макс FPS: {max(fps_log):.2f}")
                    print(f"  Мин FPS: {min(fps_log):.2f}")
                
                if not STATS_ONLY_MODE and filename and os.path.exists(filename):
                    file_size = os.path.getsize(filename) / (1024 * 1024)
                    print(f"  Размер файла: {file_size:.2f} MB")
                    print(f"  Сжатие: {(1 - file_size/(bytes_processed/(1024*1024)))*100:.1f}%")
                
                return True
        
        finally:
            sys.stdout = old_stdout
            self.logger.stop_logging()
    
    def run_default_test(self):
        """Запуск теста с параметрами по умолчанию (без меню)"""
        print("\n" + "="*80)
        print("🚀 ЗАПУСК В РЕЖИМЕ ПО УМОЛЧАНИЮ")
        print("="*80)
        print(f"Бэкенд: {DEFAULT_BACKEND}")
        print(f"Разрешение: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        print(f"Целевой FPS: {DEFAULT_FPS}")
        print(f"Длительность: {DEFAULT_DURATION} сек")
        print("="*80)
        
        self.test_resolution(
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
            self.test_resolution(backend, width, height, target_fps, duration)
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
            
            success = self.test_resolution(
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
            self.test_resolution(
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
            self.test_resolution(
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

def print_usage():
    """Вывод справки по использованию"""
    print("\n" + "="*80)
    print("ИСПОЛЬЗОВАНИЕ:")
    print("="*80)
    print("python3 camera_test.py [опции]")
    print("\nОПЦИИ:")
    print("  --default     - запуск с параметрами по умолчанию (без меню)")
    print("  --help        - показать эту справку")
    print("\nПАРАМЕТРЫ ПО УМОЛЧАНИЮ (можно изменить в шапке скрипта):")
    print(f"  DEVICE_ID = {DEVICE_ID}")
    print(f"  DEFAULT_BACKEND = {DEFAULT_BACKEND}")
    print(f"  DEFAULT_RESOLUTION = {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
    print(f"  DEFAULT_FPS = {DEFAULT_FPS}")
    print(f"  DEFAULT_DURATION = {DEFAULT_DURATION} сек")
    print("\nМАКРОС В ШАПКЕ:")
    print("  RUN_DEFAULT = True  # Всегда запускать в режиме --default")
    print("  RUN_DEFAULT = False # Интерактивный режим (по умолчанию)")
    print("="*80)

def main():
    """Основная функция"""
    
    # Проверка макроса в шапке
    if RUN_DEFAULT:
        # Принудительный режим по умолчанию
        tester = VideoCaptureTester(device_id=DEVICE_ID, output_dir=OUTPUT_DIR, log_dir=LOGS_DIR)
        tester.get_camera_info()
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