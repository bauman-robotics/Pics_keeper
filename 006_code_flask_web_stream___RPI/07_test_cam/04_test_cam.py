#!/usr/bin/env python3
"""
Тестовый скрипт для Global Shutter USB камеры
Проверяет все комбинации разрешений и кодеков
"""

import cv2
import time
import numpy as np
from tabulate import tabulate

class GlobalShutterTester:
    def __init__(self, device_path='/dev/video8'):
        self.device_path = device_path
        self.cap = None
        
        # Все поддерживаемые разрешения из вашего лога
        self.resolutions = [
            (1920, 1200),
            (1920, 1080),
            (1600, 1200),
            (1280, 960),
            (1280, 720),
            (1024, 768),
            (960, 720),
            (800, 600),
            (640, 480),
            (320, 240)
        ]
        
        # Кодеки для тестирования
        self.fourcc_codes = {
            'MJPG': cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'),
            'YUYV': cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'),
            'YU12': cv2.VideoWriter_fourcc('Y', 'U', '1', '2'),
            'NV12': cv2.VideoWriter_fourcc('N', 'V', '1', '2'),
            'BGR3': cv2.VideoWriter_fourcc('B', 'G', 'R', '3'),
            'RAW': 0x00000000  # сырой формат
        }
        
    def open_camera(self):
        """Открыть камеру"""
        print(f"📷 Открываю камеру {self.device_path}...")
        self.cap = cv2.VideoCapture(self.device_path, cv2.CAP_V4L2)
        
        if not self.cap.isOpened():
            print("❌ Не удалось открыть камеру")
            return False
        
        print("✅ Камера открыта")
        return True
    
    def close_camera(self):
        """Закрыть камеру"""
        if self.cap:
            self.cap.release()
            print("🔌 Камера закрыта")
    
    def get_fourcc_str(self, fourcc_int):
        """Конвертировать FOURCC int в строку"""
        if fourcc_int == 0:
            return "RAW"
        try:
            return chr(fourcc_int & 0xFF) + chr((fourcc_int >> 8) & 0xFF) + \
                   chr((fourcc_int >> 16) & 0xFF) + chr((fourcc_int >> 24) & 0xFF)
        except:
            return "UNKNOWN"
    
    def test_single_setup(self, width, height, fourcc_name, fourcc_value, order='normal'):
        """
        Тестирует одну комбинацию разрешения и кодека
        order: 'normal' - сначала кодек, потом разрешение
               'reverse' - сначала разрешение, потом кодек
        """
        print(f"\n🔍 ТЕСТ: {width}x{height} с кодеком {fourcc_name} (порядок: {order})")
        print("-" * 60)
        
        # Сбрасываем камеру
        self.close_camera()
        time.sleep(0.5)
        if not self.open_camera():
            return None
        
        results = {
            'width': width,
            'height': height,
            'fourcc_name': fourcc_name,
            'order': order,
            'success': False,
            'actual_width': 0,
            'actual_height': 0,
            'actual_fourcc': '',
            'actual_fps': 0,
            'frame_captured': False
        }
        
        try:
            if order == 'normal':
                # Сначала кодек
                print(f"1️⃣ Устанавливаю кодек {fourcc_name}...")
                result = self.cap.set(cv2.CAP_PROP_FOURCC, fourcc_value)
                print(f"   Результат: {result}")
                time.sleep(0.2)
                
                # Потом разрешение
                print(f"2️⃣ Устанавливаю разрешение {width}x{height}...")
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
            else:  # reverse
                # Сначала разрешение
                print(f"1️⃣ Устанавливаю разрешение {width}x{height}...")
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                time.sleep(0.2)
                
                # Потом кодек
                print(f"2️⃣ Устанавливаю кодек {fourcc_name}...")
                result = self.cap.set(cv2.CAP_PROP_FOURCC, fourcc_value)
                print(f"   Результат: {result}")
            
            # Устанавливаем FPS
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Даем время на применение
            time.sleep(0.3)
            
            # Проверяем реальные настройки
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            results['actual_width'] = actual_width
            results['actual_height'] = actual_height
            results['actual_fourcc'] = self.get_fourcc_str(actual_fourcc)
            results['actual_fps'] = actual_fps
            
            print(f"📊 Реальные настройки: {actual_width}x{actual_height}, "
                  f"кодек: {results['actual_fourcc']}, FPS: {actual_fps:.1f}")
            
            # Пробуем захватить кадр
            print("📸 Пробую захватить кадр...")
            ret, frame = self.cap.read()
            
            if ret and frame is not None:
                results['frame_captured'] = True
                h, w = frame.shape[:2]
                print(f"✅ Кадр получен! Размер: {w}x{h}, тип: {frame.dtype}")
                
                # Проверяем соответствие
                if w == width and h == height and results['actual_fourcc'] == fourcc_name:
                    results['success'] = True
                    print("🎯 ПОЛНОЕ СООТВЕТСТВИЕ!")
                elif w == width and h == height:
                    print("⚠️ Разрешение совпадает, но кодек другой")
                else:
                    print(f"⚠️ Разрешение не совпадает: {w}x{h}")
            else:
                print("❌ Не удалось получить кадр")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        return results
    
    def test_all_combinations(self):
        """Тестирует все комбинации разрешений и кодеков"""
        print("\n" + "="*80)
        print("🧪 ТЕСТИРОВАНИЕ ВСЕХ КОМБИНАЦИЙ Global Shutter камеры")
        print("="*80)
        
        all_results = []
        
        for width, height in self.resolutions:
            for fourcc_name, fourcc_value in self.fourcc_codes.items():
                # Пробуем оба порядка
                for order in ['normal', 'reverse']:
                    result = self.test_single_setup(width, height, fourcc_name, 
                                                   fourcc_value, order)
                    if result:
                        all_results.append(result)
                    
                    # Небольшая пауза между тестами
                    time.sleep(0.5)
        
        self.close_camera()
        return all_results
    
    def find_best_configuration(self):
        """Находит лучшую конфигурацию"""
        print("\n🔍 ПОИСК ЛУЧШЕЙ КОНФИГУРАЦИИ...")
        
        best_config = None
        best_score = -1
        
        for width, height in self.resolutions:
            # Пробуем MJPG в обоих порядках
            for order in ['normal', 'reverse']:
                result = self.test_single_setup(width, height, 'MJPG', 
                                               self.fourcc_codes['MJPG'], order)
                if result and result['frame_captured']:
                    # Оценка: +100 за полное соответствие, + вес разрешения
                    score = 0
                    if result['success']:
                        score += 100
                    if result['actual_width'] == width and result['actual_height'] == height:
                        score += width * height / 1000  # вес разрешения
                    
                    if score > best_score:
                        best_score = score
                        best_config = result
                
                time.sleep(0.5)
        
        return best_config
    
    def print_summary_table(self, results):
        """Печатает сводную таблицу результатов"""
        if not results:
            print("Нет результатов для отображения")
            return
        
        # Фильтруем только успешные захваты
        successful = [r for r in results if r['frame_captured']]
        
        print("\n" + "="*100)
        print("📊 СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
        print("="*100)
        
        table_data = []
        for r in successful:
            table_data.append([
                f"{r['width']}x{r['height']}",
                r['fourcc_name'],
                r['order'],
                f"{r['actual_width']}x{r['actual_height']}",
                r['actual_fourcc'],
                f"{r['actual_fps']:.1f}",
                "✅" if r['success'] else "⚠️"
            ])
        
        headers = ["Запрошено", "Кодек", "Порядок", "Получено", "Реальный кодек", "FPS", "Статус"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Статистика
        perfect = sum(1 for r in successful if r['success'])
        print(f"\n📈 Статистика:")
        print(f"   Всего тестов: {len(results)}")
        print(f"   Успешных захватов: {len(successful)}")
        print(f"   Полных совпадений: {perfect}")

def main():
    """Главная функция"""
    print("🚀 ТЕСТЕР GLOBAL SHUTTER КАМЕРЫ")
    print("=================================")
    
    # Укажите путь к вашей камере
    device_path = '/dev/video8'  # или /dev/video0
    
    tester = GlobalShutterTester(device_path)
    
    # Быстрый тест
    print("\n⚡ БЫСТРЫЙ ТЕСТ: 1024x768 с MJPG")
    result = tester.test_single_setup(1024, 768, 'MJPG', 
                                     cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'),
                                     order='normal')
    
    if result and result['frame_captured']:
        print("\n✅ Камера работает!")
    else:
        print("\n❌ Проблема с камерой")
    
    # Спросить, хочет ли пользователь полное тестирование
    response = input("\n🔄 Запустить полное тестирование всех комбинаций? (y/n): ")
    
    if response.lower() == 'y':
        print("\n⏳ Это займет несколько минут...")
        all_results = tester.test_all_combinations()
        tester.print_summary_table(all_results)
        
        # Найти лучшую конфигурацию
        best = tester.find_best_configuration()
        if best:
            print("\n" + "="*60)
            print("🏆 ЛУЧШАЯ КОНФИГУРАЦИЯ:")
            print(f"   Разрешение: {best['actual_width']}x{best['actual_height']}")
            print(f"   Кодек: {best['actual_fourcc']}")
            print(f"   FPS: {best['actual_fps']:.1f}")
            print(f"   Порядок установки: {best['order']}")
            print("="*60)
            
            # Сгенерировать конфиг
            print("\n📝 Пример конфига для вашего приложения:")
            print(f"""
camera:
  device: "{device_path}"
  width: {best['actual_width']}
  height: {best['actual_height']}
  fps: {int(best['actual_fps'])}
  fourcc: "{best['actual_fourcc']}"
  auto_exposure: 0.25  # для глобального затвора
            """)

if __name__ == "__main__":
    main()
