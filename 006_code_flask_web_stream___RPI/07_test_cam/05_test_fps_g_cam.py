#!/usr/bin/env python3
"""
Тест FPS для камеры с глобальным затвором (Global Shutter Camera)
Тестирование различных режимов: MJPEG (сжатый) и YUYV (несжатый)
"""

import cv2
import time
import numpy as np
from collections import deque
import argparse

class FPSTester:
    def __init__(self, device_id=8):
        """
        Инициализация тестера FPS
        
        Args:
            device_id: ID видеоустройства (/dev/video{device_id})
        """
        self.device_id = device_id
        self.cap = None
        self.fps_history = deque(maxlen=30)  # Храним последние 30 измерений FPS
        
    def test_mode(self, backend, width, height, target_fps, duration=5):
        """
        Тестирование конкретного режима
        
        Args:
            backend: 'MJPEG' или 'YUYV'
            width: ширина кадра
            height: высота кадра
            target_fps: целевой FPS
            duration: длительность теста в секундах
        """
        print(f"\n{'='*80}")
        print(f"🎥 Тест: {backend} | {width}x{height} | Target: {target_fps} fps")
        print(f"{'='*80}")
        
        # Определяем FourCC код для backend
        if backend.upper() == 'MJPEG':
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        else:  # YUYV
            fourcc = cv2.VideoWriter_fourcc(*'YUYV')
        
        # Открываем камеру
        self.cap = cv2.VideoCapture(self.device_id)
        
        # Устанавливаем параметры
        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, target_fps)
        
        # Проверяем, что установилось
        actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps_set = self.cap.get(cv2.CAP_PROP_FPS)
        
        fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
        
        print(f"\nРеальные параметры:")
        print(f"  Формат: {fourcc_str}")
        print(f"  Размер: {actual_width}x{actual_height}")
        print(f"  Установленный FPS: {actual_fps_set:.1f}")
        
        if actual_width != width or actual_height != height:
            print(f"⚠️  Внимание: запрошенный размер {width}x{height} не поддерживается")
            return
        
        # Счетчики для статистики
        frame_count = 0
        start_time = time.time()
        last_print = start_time
        fps_values = []
        
        print(f"\n📊 Измерение реального FPS в течение {duration} секунд...")
        print("-" * 80)
        
        try:
            while time.time() - start_time < duration:
                loop_start = time.time()
                
                # Захват кадра
                ret, frame = self.cap.read()
                
                if ret:
                    frame_count += 1
                    
                    # Расчет мгновенного FPS
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    if elapsed > 0:
                        instant_fps = frame_count / elapsed
                        self.fps_history.append(instant_fps)
                        fps_values.append(instant_fps)
                    
                    # Вывод статистики каждую секунду
                    if current_time - last_print >= 1.0:
                        avg_fps = frame_count / (current_time - start_time)
                        print(f"  Секунда {int(current_time - start_time)}: "
                              f"кадров: {frame_count}, "
                              f"средний FPS: {avg_fps:.2f}, "
                              f"мгновенный: {instant_fps:.2f}")
                        last_print = current_time
                        
                        # Показываем изображение (опционально)
                        # cv2.imshow('FPS Test', frame)
                        # if cv2.waitKey(1) & 0xFF == ord('q'):
                        #     break
                
                # Небольшая задержка для снижения нагрузки на CPU
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("\n⚠️  Тест прерван пользователем")
        
        finally:
            # Расчет итоговой статистики
            total_time = time.time() - start_time
            actual_fps = frame_count / total_time if total_time > 0 else 0
            
            print("-" * 80)
            print(f"\n📈 ИТОГОВАЯ СТАТИСТИКА:")
            print(f"  Всего кадров: {frame_count}")
            print(f"  Время теста: {total_time:.2f} сек")
            print(f"  Средний реальный FPS: {actual_fps:.2f}")
            if fps_values:
                print(f"  Максимальный FPS: {max(fps_values):.2f}")
                print(f"  Минимальный FPS: {min(fps_values):.2f}")
                print(f"  Стабильность (std dev): {np.std(fps_values):.3f}")
            
            # Оценка достижения целевого FPS
            efficiency = (actual_fps / target_fps) * 100 if target_fps > 0 else 0
            if efficiency >= 95:
                status = "✅ ОТЛИЧНО"
            elif efficiency >= 80:
                status = "⚠️  ХОРОШО"
            else:
                status = "❌ ПЛОХО"
            
            print(f"  Достижение цели: {efficiency:.1f}% - {status}")
            
            self.cap.release()
            cv2.destroyAllWindows()
    
    def run_all_tests(self):
        """Запуск всех возможных режимов для тестирования"""
        
        # Режимы для тестирования на основе вывода v4l2-ctl
        test_modes = [
            # MJPEG режимы (сжатые)
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 90, 'name': 'MJPEG Max Resolution @ 90fps'},
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 60, 'name': 'MJPEG Max Resolution @ 60fps'},
            {'backend': 'MJPEG', 'width': 1920, 'height': 1200, 'fps': 30, 'name': 'MJPEG Max Resolution @ 30fps'},
            {'backend': 'MJPEG', 'width': 1280, 'height': 720, 'fps': 90, 'name': 'MJPEG 720p @ 90fps'},
            {'backend': 'MJPEG', 'width': 640, 'height': 480, 'fps': 90, 'name': 'MJPEG VGA @ 90fps'},
            
            # YUYV режимы (несжатые)
            {'backend': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5, 'name': 'YUYV Max Resolution @ 5fps'},
            {'backend': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10, 'name': 'YUYV 720p @ 10fps'},
            {'backend': 'YUYV', 'width': 640, 'height': 480, 'fps': 30, 'name': 'YUYV VGA @ 30fps'},
            {'backend': 'YUYV', 'width': 320, 'height': 240, 'fps': 90, 'name': 'YUYV QVGA @ 90fps'},
        ]
        
        print("=" * 80)
        print("🔬 ТЕСТИРОВАНИЕ FPS ДЛЯ КАМЕРЫ С ГЛОБАЛЬНЫМ ЗАТВОРОМ")
        print("=" * 80)
        print(f"Устройство: /dev/video{self.device_id}")
        
        # Информация о камере
        test_cap = cv2.VideoCapture(self.device_id)
        if test_cap.isOpened():
            print(f"Камера успешно открыта")
            test_cap.release()
        else:
            print(f"❌ Ошибка: не удалось открыть камеру /dev/video{self.device_id}")
            return
        
        for i, mode in enumerate(test_modes, 1):
            print(f"\n{'#'*80}")
            print(f"ТЕСТ #{i}: {mode['name']}")
            print(f"{'#'*80}")
            
            self.test_mode(
                backend=mode['backend'],
                width=mode['width'],
                height=mode['height'],
                target_fps=mode['fps'],
                duration=5  # Тестируем каждый режим 5 секунд
            )
            
            # Небольшая пауза между тестами
            time.sleep(1)
        
        print("\n" + "="*80)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("="*80)

def single_test():
    """Быстрый тест одного режима"""
    parser = argparse.ArgumentParser(description='Тест FPS для камеры с глобальным затвором')
    parser.add_argument('--device', type=int, default=8, help='ID устройства (/dev/videoX)')
    parser.add_argument('--backend', type=str, default='MJPEG', choices=['MJPEG', 'YUYV'],
                       help='Формат: MJPEG (сжатый) или YUYV (несжатый)')
    parser.add_argument('--width', type=int, default=1920, help='Ширина кадра')
    parser.add_argument('--height', type=int, default=1200, help='Высота кадра')
    parser.add_argument('--fps', type=int, default=90, help='Целевой FPS')
    parser.add_argument('--duration', type=int, default=10, help='Длительность теста (сек)')
    
    args = parser.parse_args()
    
    tester = FPSTester(device_id=args.device)
    tester.test_mode(
        backend=args.backend,
        width=args.width,
        height=args.height,
        target_fps=args.fps,
        duration=args.duration
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Если есть аргументы командной строки, запускаем одиночный тест
        single_test()
    else:
        # Иначе запускаем все тесты
        tester = FPSTester(device_id=8)
        tester.run_all_tests()
