#!/usr/bin/env python3
"""
Тест FPS напрямую через V4L2 (без OpenCV)
Использует v4l2-ctl в subprocess
"""

import subprocess
import re
import time

def test_fps_v4l2(device, width, height, format, target_fps, frames=300):
    """Тест FPS через v4l2-ctl"""
    
    print(f"\n{'='*80}")
    print(f"🎥 Тест: {format} | {width}x{height} | Target: {target_fps} fps")
    print(f"{'='*80}")
    
    # Формируем команду
    cmd = [
        'v4l2-ctl', '-d', f'/dev/video{device}',
        '--set-fmt-video', f'width={width},height={height},pixelformat={format}',
        '--set-parm', str(target_fps),
        '--stream-mmap',
        '--stream-count', str(frames),
        '--stream-to=/dev/null'
    ]
    
    print(f"🚀 Запуск захвата {frames} кадров...")
    
    # Запускаем и измеряем время
    start_time = time.time()
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    elapsed = time.time() - start_time
    
    # Парсим вывод для получения FPS
    fps_values = []
    for line in result.stderr.split('\n'):
        if 'fps:' in line:
            match = re.search(r'fps:\s*(\d+\.?\d*)', line)
            if match:
                fps_values.append(float(match.group(1)))
    
    actual_fps = frames / elapsed
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"  Время захвата: {elapsed:.2f} сек")
    print(f"  Средний FPS: {actual_fps:.2f}")
    print(f"  Целевой FPS: {target_fps}")
    print(f"  Эффективность: {(actual_fps/target_fps)*100:.1f}%")
    
    if fps_values:
        print(f"  Мгновенный FPS (мин/макс): {min(fps_values):.1f} / {max(fps_values):.1f}")
    
    return actual_fps

def main():
    device = 1  # У вас /dev/video1
    
    # Тестовые режимы
    tests = [
        {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 90, 'frames': 300},
        {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 60, 'frames': 300},
        {'format': 'MJPG', 'width': 1920, 'height': 1200, 'fps': 30, 'frames': 150},
        {'format': 'MJPG', 'width': 1280, 'height': 720, 'fps': 90, 'frames': 300},
        {'format': 'MJPG', 'width': 640, 'height': 480, 'fps': 90, 'frames': 300},
        {'format': 'YUYV', 'width': 1920, 'height': 1200, 'fps': 5, 'frames': 50},
        {'format': 'YUYV', 'width': 1280, 'height': 720, 'fps': 10, 'frames': 100},
        {'format': 'YUYV', 'width': 640, 'height': 480, 'fps': 30, 'frames': 150},
        {'format': 'YUYV', 'width': 320, 'height': 240, 'fps': 90, 'frames': 300},
    ]
    
    results = []
    
    for test in tests:
        actual = test_fps_v4l2(
            device=device,
            width=test['width'],
            height=test['height'],
            format=test['format'],
            target_fps=test['fps'],
            frames=test['frames']
        )
        
        results.append({
            'name': f"{test['format']} {test['width']}x{test['height']}",
            'target': test['fps'],
            'actual': actual,
            'efficiency': (actual/test['fps'])*100
        })
        
        time.sleep(1)  # Пауза между тестами
    
    print("\n" + "="*80)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("="*80)
    
    for r in results:
        status = "✅" if r['efficiency'] > 90 else "⚠️" if r['efficiency'] > 70 else "❌"
        print(f"{status} {r['name']}: {r['actual']:.1f}/{r['target']} fps ({r['efficiency']:.1f}%)")

if __name__ == "__main__":
    main()