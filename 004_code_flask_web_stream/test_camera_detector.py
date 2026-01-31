#!/usr/bin/env python3
"""
Тестовый скрипт для проверки детектора камер
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

from camera_detector import detect_cameras

def main():
    print("🔍 Тестирование детектора камер...")
    print("=" * 50)
    
    try:
        # Детектируем камеры
        cameras = detect_cameras(max_devices=10)
        
        print("\n" + "=" * 50)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print("=" * 50)
        
        if not cameras:
            print("❌ Видеокамеры не найдены в системе")
        else:
            print(f"✅ Найдено видеокамер: {len(cameras)}")
            
            for i, cam in enumerate(cameras, 1):
                print(f"\n📹 КАМЕРА {i}: {cam['device_path']}")
                print(f"   Тип: {cam['card_type']}")
                print(f"   Драйвер: {cam['driver']}")
                print(f"   Шина: {cam['bus_info']}")
                print(f"   Разрешения: {', '.join(cam['supported_resolutions'])}")
                print(f"   FPS: {', '.join(map(str, cam['supported_fps']))}")
                
                if cam['formats']:
                    print(f"   Форматы:")
                    for fmt in cam['formats']:
                        sizes_str = ', '.join([f"{s['width']}x{s['height']}" for s in fmt['sizes']])
                        print(f"      - {fmt['name']}: {sizes_str}")
        
        print("\n" + "=" * 50)
        print("✅ Тестирование завершено")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()