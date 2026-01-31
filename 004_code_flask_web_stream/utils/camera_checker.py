#!/usr/bin/env python3
"""
Улучшенный детектор камер на основе check_cam_formats.sh
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional

class CameraChecker:
    """Класс для проверки камер на основе v4l2-ctl"""
    
    def __init__(self):
        self.logger = logging.getLogger('flask_stream')
    
    def check_device(self, device_path: str) -> Dict:
        """Проверка устройства на наличие видеозахвата"""
        try:
            # Получаем информацию об устройстве
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {'error': f"Не удалось получить информацию: {result.stderr}"}
            
            # Проверяем тип устройства
            output = result.stdout
            if 'Video Capture' in output:
                # Получаем список форматов
                formats_result = subprocess.run(
                    ['v4l2-ctl', '-d', device_path, '--list-formats'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                formats = []
                if formats_result.returncode == 0:
                    for line in formats_result.stdout.split('\n'):
                        if ':' in line and "'" in line:
                            # Извлекаем формат из строки вида "[0]: 'YUYV' (YUYV 4:2:2)"
                            match = re.search(r"'([^']+)'", line)
                            if match:
                                formats.append(match.group(1))
                
                # Получаем доступные разрешения для первого формата
                resolutions = []
                if formats:
                    formats_ext_result = subprocess.run(
                        ['v4l2-ctl', '-d', device_path, '--list-formats-ext'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if formats_ext_result.returncode == 0:
                        current_format = None
                        for line in formats_ext_result.stdout.split('\n'):
                            line = line.strip()
                            if line.startswith('[') and ']:':
                                # Начало нового формата
                                match = re.search(r'\[(\d+)\]:\s*\'(.+)\'', line)
                                if match and match.group(2) == formats[0]:
                                    current_format = match.group(2)
                                else:
                                    current_format = None
                            elif line.startswith('Size') and current_format:
                                # Размер для текущего формата
                                size_match = re.search(r'Size: Discrete (\d+)x(\d+)', line)
                                if size_match:
                                    width, height = size_match.groups()
                                    resolutions.append(f"{width}x{height}")
                
                # Считаем устройство видеокамерой только если есть форматы
                if formats:
                    return {
                        'device_path': device_path,
                        'type': 'Video Capture',
                        'formats': formats,
                        'resolutions': resolutions[:3],  # Первые 3 разрешения
                        'success': True
                    }
                else:
                    return {
                        'device_path': device_path,
                        'type': 'Other',
                        'formats': [],
                        'resolutions': [],
                        'success': False
                    }
            else:
                return {
                    'device_path': device_path,
                    'type': 'Other',
                    'formats': [],
                    'resolutions': [],
                    'success': False
                }
                
        except Exception as e:
            return {'error': f"Ошибка при проверке {device_path}: {str(e)}"}
    
    def detect_cameras(self, max_devices: int = 10) -> List[Dict]:
        """Обнаружение видеокамер"""
        cameras = []
        
        for i in range(max_devices):
            device_path = f"/dev/video{i}"
            
            # Проверяем, существует ли устройство перед логированием
            try:
                with open(device_path, 'r'):
                    pass
            except (FileNotFoundError, PermissionError):
                # Устройство не существует или нет доступа - пропускаем
                continue
            
            self.logger.info(f"🔍 Проверка устройства {device_path}")
            
            result = self.check_device(device_path)
            
            if 'error' in result:
                self.logger.debug(f"{device_path} - Ошибка: {result['error']}")
                continue
            
            if result['success']:
                self.logger.info(f"✅ {device_path} - Видеокамера найдена")
                self.logger.info(f"   Форматы: {', '.join(result['formats'])}")
                self.logger.info(f"   Разрешения: {', '.join(result['resolutions'])}")
                
                cameras.append(result)
            else:
                self.logger.debug(f"{device_path} - не видеоустройство")
        
        return cameras
    
    def log_detection_results(self, cameras: List[Dict]):
        """Логирование результатов детектирования"""
        self.logger.info("=" * 70)
        self.logger.info("🔍 РЕЗУЛЬТАТЫ ДЕТЕКТИРОВАНИЯ КАМЕР (УЛУЧШЕННЫЙ)")
        self.logger.info("=" * 70)
        
        if not cameras:
            self.logger.warning("❌ Видеокамеры не найдены в системе")
            return
        
        self.logger.info(f"📊 Найдено видеокамер: {len(cameras)}")
        
        for i, cam in enumerate(cameras, 1):
            self.logger.info(f"")
            self.logger.info(f"📹 КАМЕРА {i}: {cam['device_path']}")
            self.logger.info(f"   📴 Форматы: {', '.join(cam['formats'])}")
            
            # Сортируем разрешения по площади (от меньшего к большему)
            sorted_resolutions = sorted(cam['resolutions'], key=lambda res: self._calculate_resolution_area(res))
            
            if sorted_resolutions:
                self.logger.info(f"   📋 Разрешения:")
                for resolution in sorted_resolutions:
                    self.logger.info(f"      • {resolution}")
            else:
                self.logger.info(f"   📋 Разрешения: нет доступных")
        
        self.logger.info("=" * 70)
    
    def _calculate_resolution_area(self, resolution: str) -> int:
        """Рассчитывает площадь разрешения для сортировки"""
        try:
            width, height = map(int, resolution.split('x'))
            return width * height
        except (ValueError, TypeError):
            return 0

def check_cameras(max_devices: int = 10) -> List[Dict]:
    """Функция для быстрой проверки камер"""
    checker = CameraChecker()
    cameras = checker.detect_cameras(max_devices)
    checker.log_detection_results(cameras)
    return cameras

def main():
    """Тестовая функция"""
    print("🔍 Тестирование улучшенного детектора камер...")
    print("=" * 50)
    
    try:
        cameras = check_cameras(max_devices=10)
        
        print("\n" + "=" * 50)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
        print("=" * 50)
        
        if not cameras:
            print("❌ Видеокамеры не найдены в системе")
        else:
            print(f"✅ Найдено видеокамер: {len(cameras)}")
            
            for i, cam in enumerate(cameras, 1):
                print(f"\n📹 КАМЕРА {i}: {cam['device_path']}")
                print(f"   Форматы: {', '.join(cam['formats'])}")
                print(f"   Разрешения: {', '.join(cam['resolutions'])}")
        
        print("\n" + "=" * 50)
        print("✅ Тестирование завершено")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()