#!/usr/bin/env python3
"""
Тест FPS и захват видео через V4L2 (без OpenCV)
Сохраняет видео для последующего анализа

v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-ctrls
v4l2-ctl -d /dev/video8 --all
media-ctl -p -d /dev/media5
"""

import subprocess
import re
import time
import os
from datetime import datetime

class V4L2VideoTester:
    def __init__(self, device=1, output_dir="v4l2_test_videos"):
        """
        Инициализация тестера
        
        Args:
            device: номер устройства (/dev/video{device})
            output_dir: директория для сохранения видео
        """
        self.device = device
        self.output_dir = output_dir
        
        # Создаем директорию если её нет
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"📁 Создана директория: {output_dir}")
    
    def get_device_info(self):
        """Получение информации об устройстве"""
        print("\n" + "="*80)
        print("🔍 ИНФОРМАЦИЯ ОБ УСТРОЙСТВЕ")
        print("="*80)
        
        try:
            # Информация о драйвере
            result = subprocess.run(
                ['v4l2-ctl', '-d', f'/dev/video{self.device}', '--all'],
                capture_output=True,
                text=True
            )
            
            # Извлекаем основные параметры
            for line in result.stdout.split('\n'):
                if 'Driver name' in line or 'Card type' in line or 'Width/Height' in line:
                    print(f"  {line.strip()}")
            
            print("\n📋 Доступные форматы:")
            # Показываем первые несколько форматов
            result = subprocess.run(
                ['v4l2-ctl', '-d', f'/dev/video{self.device}', '--list-formats-ext'],
                capture_output=True,
                text=True
            )
            lines = result.stdout.split('\n')[:20]  # Первые 20 строк
            for line in lines:
                if 'MJPG' in line or 'YUYV' in line or 'Size' in line or 'Interval' in line:
                    print(f"  {line.strip()}")
                    
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
    
    def capture_video(self, format, width, height, target_fps, duration=5):
        """
        Захват видео с указанными параметрами
        
        Args:
            format: 'MJPG' или 'YUYV'
            width: ширина
            height: высота
            target_fps: целевой FPS
            duration: длительность записи в секундах
        """
        print(f"\n{'#'*80}")
        print(f"🎥 ТЕСТ: {format} | {width}x{height} | {target_fps} fps | {duration} сек")
        print(f"{'#'*80}")
        
        # Формируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format.upper() == 'MJPG':
            ext = 'mjpg'  # MJPEG формат
            pixelformat = 'MJPG'
        else:
            ext = 'yuv'   # Сырой YUYV формат
            pixelformat = 'YUYV'
        
        filename = f"{self.output_dir}/{format}_{width}x{height}_{target_fps}fps_{timestamp}.{ext}"
        info_filename = f"{self.output_dir}/{format}_{width}x{height}_{target_fps}fps_{timestamp}.txt"
        
        # Рассчитываем количество кадров
        frame_count = int(target_fps * duration)
        
        print(f"📹 Параметры захвата:")
        print(f"  Устройство: /dev/video{self.device}")
        print(f"  Формат: {format}")
        print(f"  Размер: {width}x{height}")
        print(f"  Целевой FPS: {target_fps}")
        print(f"  Кадров: {frame_count}")
        print(f"  Длительность: {duration} сек")
        print(f"  Файл видео: {filename}")
        
        # Формируем команду v4l2-ctl
        cmd = [
            'v4l2-ctl', '-d', f'/dev/video{self.device}',
            '--set-fmt-video', f'width={width},height={height},pixelformat={pixelformat}',
            '--set-parm', str(target_fps),
            '--stream-mmap',
            '--stream-count', str(frame_count),
            '--stream-to', filename
        ]
        
        # Сохраняем информацию о тесте
        with open(info_filename, 'w') as f:
            f.write(f"Тест захвата видео через V4L2\n")
            f.write(f"Время: {datetime.now()}\n")
            f.write(f"Устройство: /dev/video{self.device}\n")
            f.write(f"Формат: {format}\n")
            f.write(f"Разрешение: {width}x{height}\n")
            f.write(f"Целевой FPS: {target_fps}\n")
            f.write(f"Длительность: {duration} сек\n")
            f.write(f"Ожидаемое количество кадров: {frame_count}\n")
            f.write("-" * 60 + "\n")
        
        print(f"\n⏱️  Захват {duration} секунд...")
        
        # Запускаем захват с измерением времени
        start_time = time.time()
        
        try:
            # Запускаем процесс и собираем вывод для анализа FPS
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True
            )
            
            # Собираем статистику в реальном времени
            fps_values = []
            frame_times = []
            
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                    
                if 'fps:' in line:
                    match = re.search(r'fps:\s*(\d+\.?\d*)', line)
                    if match:
                        fps = float(match.group(1))
                        fps_values.append(fps)
                        
                    # Парсим время между кадрами
                    match = re.search(r'delta:\s*(\d+\.?\d*)\s*ms', line)
                    if match:
                        delta = float(match.group(1))
                        frame_times.append(delta)
            
            # Ждем завершения
            process.wait()
            
            elapsed = time.time() - start_time
            
            # Считаем реальный размер файла
            file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            file_size_mb = file_size / (1024 * 1024)
            
            # Сохраняем статистику
            with open(info_filename, 'a') as f:
                f.write(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТА:\n")
                f.write(f"Время захвата: {elapsed:.2f} сек\n")
                f.write(f"Ожидалось кадров: {frame_count}\n")
                f.write(f"Размер файла: {file_size_mb:.2f} MB\n")
                
                if fps_values:
                    avg_fps = sum(fps_values) / len(fps_values)
                    f.write(f"Средний FPS (из лога): {avg_fps:.2f}\n")
                    f.write(f"Макс FPS: {max(fps_values):.2f}\n")
                    f.write(f"Мин FPS: {min(fps_values):.2f}\n")
                    
                if frame_times:
                    avg_delta = sum(frame_times) / len(frame_times)
                    f.write(f"Среднее время между кадрами: {avg_delta:.3f} ms\n")
            
            # Выводим результаты
            print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТА:")
            print(f"  Время захвата: {elapsed:.2f} сек")
            print(f"  Ожидалось кадров: {frame_count}")
            print(f"  Размер файла: {file_size_mb:.2f} MB")
            
            if fps_values:
                avg_fps = sum(fps_values) / len(fps_values)
                print(f"  Средний FPS: {avg_fps:.2f}")
                print(f"  Макс FPS: {max(fps_values):.2f}")
                print(f"  Мин FPS: {min(fps_values):.2f}")
                print(f"  Эффективность: {(avg_fps/target_fps)*100:.1f}%")
            
            print(f"  Инфо файл: {info_filename}")
            print(f"  Видео файл: {filename}")
            
            return {
                'success': True,
                'filename': filename,
                'info_file': info_filename,
                'size_mb': file_size_mb,
                'avg_fps': avg_fps if fps_values else 0,
                'elapsed': elapsed
            }
            
        except Exception as e:
            print(f"❌ Ошибка при захвате: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_test_suite(self, short_test=False):
        """Запуск набора тестов"""
        
        duration = 3 if short_test else 5
        
        print("\n" + "="*80)
        print("🚀 ЗАПУСК ТЕСТОВ ЗАХВАТА ВИДЕО ЧЕРЕЗ V4L2")
        print(f"Длительность каждого теста: {duration} секунд")
        print("="*80)
        
        # Тестовые режимы на основе вашей камеры
        test_modes = [
            # MJPEG режимы
            {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 90},
            {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 60},
            {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 30},
            {'format': 'MJPG', 'width': 1280, 'height': 720, 'fps': 90},
            {'format': 'MJPG', 'width': 1280, 'height': 720, 'fps': 60},
            {'format': 'MJPG', 'width': 640, 'height': 480, 'fps': 90},
            
            # YUYV режимы
            {'format': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5},
            {'format': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10},
            {'format': 'YUYV', 'width': 640, 'height': 480, 'fps': 30},
            {'format': 'YUYV', 'width': 320, 'height': 240, 'fps': 90},
        ]
        
        results = []
        
        for i, mode in enumerate(test_modes, 1):
            print(f"\n{'#'*80}")
            print(f"ТЕСТ #{i}: {mode['format']} {mode['width']}x{mode['height']} @ {mode['fps']}fps")
            print(f"{'#'*80}")
            
            result = self.capture_video(
                format=mode['format'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
            
            results.append({
                'test': f"{mode['format']} {mode['width']}x{mode['height']}",
                'target_fps': mode['fps'],
                'actual_fps': result.get('avg_fps', 0) if result['success'] else 0,
                'success': result['success'],
                'filename': result.get('filename', '')
            })
            
            # Пауза между тестами
            time.sleep(2)
        
        # Итоговая сводка
        print("\n" + "="*80)
        print("📊 ИТОГОВАЯ СВОДКА")
        print("="*80)
        
        for r in results:
            if r['success'] and r['actual_fps'] > 0:
                efficiency = (r['actual_fps'] / r['target_fps']) * 100
                status = "✅" if efficiency > 90 else "⚠️" if efficiency > 70 else "❌"
                print(f"{status} {r['test']}: {r['actual_fps']:.1f}/{r['target_fps']} fps ({efficiency:.1f}%)")
            else:
                print(f"❌ {r['test']}: ОШИБКА")
        
        print(f"\n📁 Все видео сохранены в: {self.output_dir}")
        print("="*80)

def main():
    """Основная функция"""
    
    print("\n" + "="*80)
    print("🎬 ТЕСТ ЗАХВАТА ВИДЕО ЧЕРЕЗ V4L2")
    print("="*80)
    
    # Параметры
    DEVICE = 1  # У вас /dev/video1
    DEVICE = 16  # У вас /dev/video16
    OUTPUT_DIR = "v4l2_capture_test"
    
    # Создаем тестер
    tester = V4L2VideoTester(device=DEVICE, output_dir=OUTPUT_DIR)
    
    # Получаем информацию об устройстве
    tester.get_device_info()
    
    # Меню выбора
    print("\nВыберите режим тестирования:")
    print("1. Полное тестирование (5 сек на режим)")
    print("2. Быстрое тестирование (3 сек на режим)")
    print("3. Только MJPEG режимы")
    print("4. Только YUYV режимы")
    print("5. Одиночный тест (свои параметры)")
    
    choice = input("\nВаш выбор (1-5) [по умолчанию 1]: ").strip() or "1"
    
    if choice == "1":
        tester.run_test_suite(short_test=False)
    elif choice == "2":
        tester.run_test_suite(short_test=True)
    elif choice == "3":
        # Только MJPEG
        duration = 5
        modes = [
            {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 90},
            {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 60},
            {'format': 'MJPG', 'width': 1280, 'height': 720, 'fps': 90},
            {'format': 'MJPG', 'width': 640, 'height': 480, 'fps': 90},
        ]
        for mode in modes:
            tester.capture_video(
                format=mode['format'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
    elif choice == "4":
        # Только YUYV
        duration = 5
        modes = [
            {'format': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5},
            {'format': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10},
            {'format': 'YUYV', 'width': 640, 'height': 480, 'fps': 30},
            {'format': 'YUYV', 'width': 320, 'height': 240, 'fps': 90},
        ]
        for mode in modes:
            tester.capture_video(
                format=mode['format'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=duration
            )
    elif choice == "5":
        # Одиночный тест
        print("\nВведите параметры теста:")
        format = input("Формат (MJPG/YUYV) [MJPG]: ").strip() or "MJPG"
        width = int(input("Ширина [1920]: ").strip() or "1920")
        height = int(input("Высота [1200]: ").strip() or "1200")
        fps = int(input("Целевой FPS [90]: ").strip() or "90")
        duration = int(input("Длительность (сек) [5]: ").strip() or "5")
        
        tester.capture_video(
            format=format.upper(),
            width=width,
            height=height,
            target_fps=fps,
            duration=duration
        )
    
    print(f"\n✅ Все тесты завершены!")
    print(f"📁 Видео сохранены в: {OUTPUT_DIR}")
    print("\n💡 Для анализа видео на другом компьютере:")
    print("   MJPEG файлы можно открыть любым видеоплеером")
    print("   YUYV файлы нужно конвертировать:")
    print("   ffmpeg -f rawvideo -vcodec rawvideo -s 640x480 -pix_fmt yuyv422 -i file.yuv -c:v libx264 output.mp4")

if __name__ == "__main__":
    main()