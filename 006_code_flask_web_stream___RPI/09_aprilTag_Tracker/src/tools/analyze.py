#!/usr/bin/env python3
"""
Инструмент для анализа логов осей
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def analyze_axes_log(log_file):
    """Анализ лог-файла с данными об осях"""
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Пропускаем заголовок
    data = []
    for line in lines:
        if line.startswith('{'):
            try:
                data.append(json.loads(line))
            except:
                continue
    
    if len(data) < 2:
        print("Not enough data points")
        return
    
    # Извлекаем координаты
    times = [d['timestamp'] for d in data]
    marker_x = [d['marker_center'][0] for d in data]
    marker_y = [d['marker_center'][1] for d in data]
    z_x = [d['axis_Z_end'][0] for d in data]
    z_y = [d['axis_Z_end'][1] for d in data]
    
    # Создаем графики
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Траектория маркера
    axes[0,0].scatter(marker_x, marker_y, c=range(len(marker_x)), cmap='viridis')
    axes[0,0].set_title('Marker Center Trajectory')
    axes[0,0].set_xlabel('X (pixels)')
    axes[0,0].set_ylabel('Y (pixels)')
    axes[0,0].invert_yaxis()  # Y увеличивается вниз в OpenCV
    axes[0,0].grid(True)
    
    # Траектория конца оси Z
    axes[0,1].scatter(z_x, z_y, c=range(len(z_x)), cmap='plasma')
    axes[0,1].set_title('Z Axis Endpoint Trajectory')
    axes[0,1].set_xlabel('X (pixels)')
    axes[0,1].set_ylabel('Y (pixels)')
    axes[0,1].invert_yaxis()
    axes[0,1].grid(True)
    
    # Расстояние от маркера до конца оси Z
    distances = [np.sqrt((mx - zx)**2 + (my - zy)**2) 
                 for mx, my, zx, zy in zip(marker_x, marker_y, z_x, z_y)]
    
    axes[1,0].plot(distances)
    axes[1,0].set_title('Z Axis Length (pixels)')
    axes[1,0].set_xlabel('Frame')
    axes[1,0].set_ylabel('Length (pixels)')
    axes[1,0].grid(True)
    
    # Направление оси Z (угол)
    angles = [np.degrees(np.arctan2(zy - my, zx - mx)) 
              for mx, my, zx, zy in zip(marker_x, marker_y, z_x, z_y)]
    
    axes[1,1].plot(angles)
    axes[1,1].set_title('Z Axis Direction (degrees)')
    axes[1,1].set_xlabel('Frame')
    axes[1,1].set_ylabel('Angle (degrees)')
    axes[1,1].grid(True)
    
    plt.tight_layout()
    plt.savefig('axes_analysis.png')
    plt.show()
    
    # Статистика
    print(f"\n📊 Axis Statistics:")
    print(f"   Frames analyzed: {len(data)}")
    print(f"   Z axis visible: {sum(1 for d in data if d['axis_Z_visible'])}/{len(data)}")
    print(f"   Average Z length: {np.mean(distances):.1f} pixels")
    print(f"   Z length std: {np.std(distances):.1f} pixels")


if __name__ == "__main__":
    log_file = Path("logs/axes_debug.log")
    if log_file.exists():
        analyze_axes_log(log_file)
    else:
        print(f"Log file not found: {log_file}")
