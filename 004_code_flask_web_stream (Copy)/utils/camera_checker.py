#!/usr/bin/env python3
"""
Упрощенный детектор камер для быстрой работы в Flask
"""

import subprocess
import re
import logging
import os
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

class CameraChecker:
    """Класс для быстрой проверки камер"""
    
    def __init__(self, log_level=logging.WARNING):
        self.logger = logging.getLogger('flask_stream')
        self.logger.setLevel(log_level)
        self.cache_time = 0
        self.cached_cameras = None
        self.CACHE_TTL = 60  # Кэшировать на 60 секунд
    
    def get_cached_cameras(self) -> List[Dict]:
        """Получение кэшированного списка камер"""
        current_time = time.time()
        
        if (self.cached_cameras is not None and 
            current_time - self.cache_time < self.CACHE_TTL):
            return self.cached_cameras
        
        # Обновляем кэш
        self.cached_cameras = self._detect_cameras_fast()
        self.cache_time = current_time
        return self.cached_cameras
    
    def detect_cameras(self) -> List[Dict]:
        """Обнаружение видеокамер (публичный интерфейс)"""
        return self.get_cached_cameras()
    
    def _detect_cameras_fast(self, max_workers: int = 4) -> List[Dict]:
        """Быстрое обнаружение камер с многопоточностью"""
        cameras = []
        video_devices = self._find_video_devices()
        
        if not video_devices:
            return []
        
        # Проверяем устройства параллельно с ограничением по времени
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(self._quick_check_device, device): device 
                for device in video_devices[:10]  # Проверяем только первые 10
            }
            
            for future in as_completed(future_to_device, timeout=10):
                device = future_to_device[future]
                try:
                    result = future.result(timeout=2)
                    if result.get('is_camera', False):
                        cameras.append(result)
                except (TimeoutError, Exception) as e:
                    self.logger.debug(f"Пропуск {device}: {e}")
                    continue
        
        return cameras
    
    def _find_video_devices(self) -> List[str]:
        """Найти видео устройства"""
        devices = []
        
        # Проверяем стандартные пути
        for i in range(10):  # Проверяем до video9
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                devices.append(device_path)
        
        return devices
    
    def _quick_check_device(self, device_path: str) -> Dict:
        """Быстрая проверка устройства"""
        try:
            # Простая проверка: пытаемся получить информацию
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--info'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode != 0:
                return {
                    'device_path': device_path,
                    'is_camera': False,
                    'error': 'Cannot get device info'
                }
            
            output = result.stdout
            
            # Проверяем, является ли это видео устройством захвата
            is_camera = 'Video Capture' in output
            
            # Получаем базовую информацию
            info = {
                'device_path': device_path,
                'is_camera': is_camera,
                'formats': [],
                'resolutions': []
            }
            
            if is_camera:
                # Получаем название камеры
                info['name'] = self._get_camera_name_fast(device_path)
                
                # Получаем основные форматы (ограниченно)
                formats = self._get_simple_formats(device_path)
                if formats:
                    info['formats'] = formats[:3]  # Только 3 формата
                
                # Получаем основные разрешения (ограниченно)
                resolutions = self._get_simple_resolutions(device_path)
                if resolutions:
                    info['resolutions'] = resolutions[:5]  # Только 5 разрешений
            
            return info
            
        except subprocess.TimeoutExpired:
            return {
                'device_path': device_path,
                'is_camera': False,
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'device_path': device_path,
                'is_camera': False,
                'error': str(e)
            }
    
    def _get_camera_name_fast(self, device_path: str) -> str:
        """Получить название камеры быстро"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '-D'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Card type' in line or 'Driver name' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            return parts[1].strip()
        except:
            pass
        
        return device_path
    
    def _get_simple_formats(self, device_path: str) -> List[str]:
        """Получить простой список форматов"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--list-formats'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            formats = []
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line and "'" in line:
                        match = re.search(r"'([^']+)'", line)
                        if match:
                            formats.append(match.group(1))
            
            return formats
        except:
            return []
    
    def _get_simple_resolutions(self, device_path: str) -> List[str]:
        """Получить простой список разрешений (только для MJPG формата)"""
        try:
            cmd = f"v4l2-ctl -d {device_path} --list-formats-ext 2>/dev/null | grep -A5 'MJPG' | grep 'Size:'"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=1
            )
            
            resolutions = []
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(r'Size:\s*Discrete\s*(\d+x\d+)', line)
                    if match:
                        resolutions.append(match.group(1))
            
            # Если не нашли MJPG, пробуем YUYV
            if not resolutions:
                cmd = f"v4l2-ctl -d {device_path} --list-formats-ext 2>/dev/null | grep -A5 'YUYV' | grep 'Size:'"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        match = re.search(r'Size:\s*Discrete\s*(\d+x\d+)', line)
                        if match:
                            resolutions.append(match.group(1))
            
            # Удаляем дубликаты и сортируем по размеру
            unique_res = list(set(resolutions))
            unique_res.sort(key=lambda x: self._resolution_area(x), reverse=True)
            
            return unique_res
            
        except:
            return []
    
    def _resolution_area(self, resolution: str) -> int:
        """Вычислить площадь разрешения для сортировки"""
        try:
            w, h = map(int, resolution.split('x'))
            return w * h
        except:
            return 0
    
    def get_quick_cameras_list(self) -> List[Dict]:
        """Очень быстрый список камер (для API)"""
        cameras = []
        video_devices = self._find_video_devices()
        
        for device in video_devices[:5]:  # Только первые 5
            # Простейшая проверка - существование и возможность чтения
            try:
                with open(device, 'r'):
                    pass
                
                # Простая проверка на видео устройство
                try:
                    result = subprocess.run(
                        ['v4l2-ctl', '-d', device, '--info'],
                        capture_output=True,
                        text=True,
                        timeout=1
                    )
                    
                    is_camera = 'Video Capture' in result.stdout if result.returncode == 0 else False
                    
                    cameras.append({
                        'device_path': device,
                        'name': device,  # Просто путь как имя
                        'formats': ['MJPG', 'YUYV'] if is_camera else [],
                        'resolutions': ['640x480', '320x240'] if is_camera else [],
                        'is_camera': is_camera
                    })
                except:
                    cameras.append({
                        'device_path': device,
                        'name': device,
                        'formats': [],
                        'resolutions': [],
                        'is_camera': False
                    })
                    
            except:
                continue
        
        return cameras