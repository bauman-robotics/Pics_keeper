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
        self.camera_names = self._get_camera_names()
    
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
                
                # Получаем доступные разрешения и FPS для всех форматов
                resolutions_with_fps = self._get_camera_resolutions_with_fps(device_path)
                resolutions = []
                if formats and resolutions_with_fps:
                    # Берем первые 3 разрешения из первого формата
                    first_format = formats[0]
                    if first_format in resolutions_with_fps:
                        resolutions = list(resolutions_with_fps[first_format].keys())[:3]
                
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
            # Получаем название камеры
            camera_name = self._get_camera_name(cam['device_path'])
            self.logger.info(f"📹 КАМЕРА {i}: {cam['device_path']} ({camera_name})")
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
    
    def log_detection_results_with_fps(self, cameras: List[Dict]):
        """Логирование результатов детектирования с FPS"""
        self.logger.info("=" * 80)
        self.logger.info("🔍 РЕЗУЛЬТАТЫ ДЕТЕКТИРОВАНИЯ КАМЕР С FPS")
        self.logger.info("=" * 80)
        
        if not cameras:
            self.logger.warning("❌ Видеокамеры не найдены в системе")
            return
        
        self.logger.info(f"📊 Найдено видеокамер: {len(cameras)}")
        
        for i, cam in enumerate(cameras, 1):
            self.logger.info(f"")
            # Получаем название камеры
            camera_name = self._get_camera_name(cam['device_path'])
            self.logger.info(f"📹 КАМЕРА {i}: {cam['device_path']} ({camera_name})")
            
            # Получаем информацию о форматах с FPS
            resolutions_with_fps = self._get_camera_resolutions_with_fps(cam['device_path'])
            
            if resolutions_with_fps:
                self.logger.info(f"   📴 Форматы и FPS:")
                
                for fmt, resolutions in resolutions_with_fps.items():
                    self.logger.info(f"      ┌─ Формат: {fmt}")
                    
                    for res, fps_list in resolutions.items():
                        # Сортируем FPS по убыванию
                        fps_list_sorted = sorted(fps_list, key=lambda x: float(x), reverse=True)
                        fps_str = ', '.join([f"{fps}fps" for fps in fps_list_sorted])
                        self.logger.info(f"      ├─ {res}: {fps_str}")
                    
                    # Добавляем пустую строку между форматами
                    if list(resolutions_with_fps.keys())[-1] != fmt:
                        self.logger.info(f"      │")
            else:
                self.logger.info(f"   📴 Форматы: {', '.join(cam['formats'])}")
                self.logger.info(f"   📋 Разрешения: нет доступных данных о FPS")
        
        self.logger.info("=" * 80)
    
    def _get_camera_names(self) -> Dict[str, str]:
        """Получение названий камер по устройствам"""
        cameras = {}
        try:
            # Получаем список всех видеоустройств
            result = subprocess.run(['v4l2-ctl', '--list-devices'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                # Парсим вывод
                current_camera = None
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('\t'):
                        # Это название камеры
                        current_camera = line.strip()
                    elif line.strip() and line.startswith('\t'):
                        # Это устройство камеры
                        device_match = re.search(r'/dev/video\d+', line)
                        if device_match and current_camera:
                            device = device_match.group()
                            cameras[device] = current_camera
        except Exception as e:
            self.logger.debug(f"Ошибка при получении названий камер: {e}")
        
        return cameras
    
    def _get_camera_name(self, device_path: str) -> str:
        """Получение названия камеры по устройству"""
        return self.camera_names.get(device_path, "Неизвестная камера")
    
    def _get_camera_resolutions_with_fps(self, device_path: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Получить разрешения и FPS для всех форматов камеры
        
        Возвращает:
            {
                'YUYV': {
                    '640x480': ['30.000', '25.000', ...],
                    '1280x720': ['10.000', ...]
                },
                'MJPG': {
                    '640x480': ['30.000', '25.000', ...],
                    '1280x720': ['30.000', ...]
                }
            }
        """
        result = {}
        
        # Получаем подробную информацию о форматах
        try:
            cmd = f"v4l2-ctl -d {device_path} --list-formats-ext"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
            
            current_format = None
            current_resolution = None
            
            for line in output.split('\n'):
                line = line.strip()
                
                # Определяем формат
                format_match = re.search(r"\[\d+\]: '([^']+)'", line)
                if format_match:
                    current_format = format_match.group(1)
                    result[current_format] = {}
                    continue
                
                # Определяем разрешение
                res_match = re.search(r"Size: Discrete (\d+x\d+)", line)
                if res_match:
                    current_resolution = res_match.group(1)
                    result[current_format][current_resolution] = []
                    continue
                
                # Определяем FPS
                fps_match = re.search(r"\(([\d\.]+) fps\)", line)
                if fps_match and current_resolution:
                    fps = fps_match.group(1)
                    # Оставляем только целые числа или одно десятичное значение
                    fps_clean = f"{float(fps):.1f}"
                    if fps_clean not in result[current_format][current_resolution]:
                        result[current_format][current_resolution].append(fps_clean)
                        
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Ошибка получения FPS для {device_path}: {e}")
        
        return result
    
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