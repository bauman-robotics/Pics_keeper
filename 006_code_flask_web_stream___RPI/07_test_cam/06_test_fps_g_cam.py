#!/usr/bin/env python3
"""
Скрипт для тестового захвата видео в разных разрешениях
Без предпросмотра, только запись для последующего анализа
"""

import cv2
import time
import os
import subprocess
from datetime import datetime

class VideoCaptureTester:
    def __init__(self, device_id=8, output_dir="test_videos"):
        """
        Инициализация тестера
        
        Args:
            device_id: ID видеоустройства (/dev/video{device_id})
            output_dir: директория для сохранения видео
        """
        self.device_id = device_id
        self.output_dir = output_dir
        
        # Создаем директорию для видео если её нет
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Создана директория: {output_dir}")
    
    def get_camera_info(self):
        """Получение информации о камере"""
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
    
    def test_resolution(self, backend, width, height, target_fps, duration=10, codec=None):
        """
        Тестирование конкретного разрешения с записью видео
        
        Args:
            backend: 'MJPEG' или 'YUYV'
            width: ширина
            height: высота
            target_fps: целевой FPS
            duration: длительность записи в секундах
            codec: кодек для сохранения (по умолчанию MJPG для MJPEG, RAW для YUYV)
        """
        print(f"\n{'#'*80}")
        print(f"🎥 ТЕСТ: {backend} | {width}x{height} | {target_fps} fps | {duration} сек")
        print(f"{'#'*80}")
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backend.upper() == 'MJPEG':
            ext = 'avi'
            fourcc_code = cv2.VideoWriter_fourcc(*'MJPG')
        else:  # YUYV
            ext = 'avi'
            fourcc_code = cv2.VideoWriter_fourcc(*'FFV1')  # Lossless codec для YUYV
        
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
        
        # Даем камере время на применение настроек
        time.sleep(1)
        
        # Проверяем реальные параметры
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps_set = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"\n📊 Реальные параметры:")
        print(f"  Размер: {actual_width}x{actual_height}")
        print(f"  Установленный FPS: {actual_fps_set:.1f}")
        
        # Проверяем поддерживается ли разрешение
        if actual_width != width or actual_height != height:
            print(f"❌ Размер {width}x{height} не поддерживается в формате {backend}")
            print(f"   Камера установила {actual_width}x{actual_height}")
            cap.release()
            return False
        
        # Создаем VideoWriter
        if backend.upper() == 'YUYV':
            # Для YUYV используем больший битрейт для сохранения качества
            writer = cv2.VideoWriter(filename, fourcc_code, target_fps, (actual_width, actual_height))
        else:
            writer = cv2.VideoWriter(filename, fourcc_code, target_fps, (actual_width, actual_height))
        
        if not writer.isOpened():
            print("❌ Не удалось создать VideoWriter")
            cap.release()
            return False
        
        print(f"💾 Сохранение в: {filename}")
        print(f"\n⏱️  Запись {duration} секунд...")
        
        # Статистика
        frame_count = 0
        start_time = time.time()
        fps_log = []
        last_log_time = start_time
        
        try:
            while time.time() - start_time < duration:
                ret, frame = cap.read()
                
                if ret:
                    frame_count += 1
                    writer.write(frame)
                    
                    # Логируем FPS каждые 2 секунды
                    current_time = time.time()
                    if current_time - last_log_time >= 2.0:
                        elapsed = current_time - start_time
                        current_fps = frame_count / elapsed
                        fps_log.append(current_fps)
                        print(f"  Секунда {int(elapsed)}: {current_fps:.2f} fps (кадров: {frame_count})")
                        last_log_time = current_time
                else:
                    print("⚠️  Пропуск кадра")
                    time.sleep(0.001)
                    
        except KeyboardInterrupt:
            print("\n⏹️  Запись прервана пользователем")
        
        finally:
            # Завершаем запись
            total_time = time.time() - start_time
            actual_fps = frame_count / total_time if total_time > 0 else 0
            
            writer.release()
            cap.release()
            
            print(f"\n📊 ИТОГИ ТЕСТА:")
            print(f"  Всего кадров: {frame_count}")
            print(f"  Время записи: {total_time:.2f} сек")
            print(f"  Средний FPS: {actual_fps:.2f}")
            print(f"  Целевой FPS: {target_fps}")
            print(f"  Эффективность: {(actual_fps/target_fps)*100:.1f}%")
            
            if fps_log:
                print(f"  Макс FPS: {max(fps_log):.2f}")
                print(f"  Мин FPS: {min(fps_log):.2f}")
            
            # Размер файла
            if os.path.exists(filename):
                file_size = os.path.getsize(filename) / (1024 * 1024)  # в MB
                print(f"  Размер файла: {file_size:.2f} MB")
            
            return True
    
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
        
        # Режимы для тестирования
        test_modes = [
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
        
        results = []
        
        for i, mode in enumerate(test_modes, 1):
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
    
    def cleanup_old_videos(self, days=7):
        """Удаление старых видеофайлов"""
        import shutil
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.isfile(filepath):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if mtime < cutoff:
                    os.remove(filepath)
                    print(f"Удален старый файл: {filename}")

def main():
    """Основная функция"""
    
    print("\n" + "="*80)
    print("🎬 ТЕСТОВЫЙ ЗАХВАТ ВИДЕО С КАМЕРЫ ГЛОБАЛЬНОГО ЗАТВОРА")
    print("="*80)
    
    # Параметры
    DEVICE_ID = 8
    OUTPUT_DIR = "camera_test_videos"
    
    # Создаем тестер
    tester = VideoCaptureTester(device_id=DEVICE_ID, output_dir=OUTPUT_DIR)
    
    # Получаем информацию о камере
    tester.get_camera_info()
    
    # Спрашиваем режим тестирования
    print("\nВыберите режим тестирования:")
    print("1. Полное тестирование (10 сек на режим)")
    print("2. Быстрое тестирование (5 сек на режим)")
    print("3. Только MJPEG режимы")
    print("4. Только YUYV режимы")
    
    choice = input("\nВаш выбор (1-4) [по умолчанию 2]: ").strip() or "2"
    
    if choice == "1":
        duration = 10
        tester.run_all_tests(short_test=False)
    elif choice == "2":
        duration = 5
        tester.run_all_tests(short_test=True)
    elif choice == "3":
        # Только MJPEG
        modes = [
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90},
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60},
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30},
            {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90},
            {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90},
        ]
        for mode in modes:
            tester.test_resolution(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=10
            )
    elif choice == "4":
        # Только YUYV
        modes = [
            {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5},
            {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10},
            {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30},
            {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90},
        ]
        for mode in modes:
            tester.test_resolution(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=10
            )
    
    print(f"\n✅ Все тесты завершены!")
    print(f"📁 Видео сохранены в: {OUTPUT_DIR}")
    print("\nДля анализа видео можно использовать:")
    print("  ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 файл.avi")
    print("  или просто открыть в медиаплеере на другом компьютере")

if __name__ == "__main__":
    main()