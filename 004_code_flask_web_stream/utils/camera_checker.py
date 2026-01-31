#!/usr/bin/env python3
"""
Упрощенный детектор камер для быстрой работы в Flask
"""

import subprocess
import re
import logging  # ← ДОБАВЬТЕ ЭТОТ ИМПОРТ
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
        self.CACHE_TTL = 60
    
    def detect_cameras(self) -> List[Dict]:
        """Обнаружение РЕАЛЬНЫХ видеокамер"""
        cameras = self.get_cached_cameras()
        return self._filter_real_cameras(cameras)
    
    def get_cached_cameras(self) -> List[Dict]:
        """Получение кэшированного списка камер"""
        current_time = time.time()
        
        if (self.cached_cameras is not None and 
            current_time - self.cache_time < self.CACHE_TTL):
            return self.cached_cameras
        
        # Обновляем кэш
        self.cached_cameras = self._detect_all_devices()
        self.cache_time = current_time
        return self.cached_cameras
    
    def _detect_all_devices(self) -> List[Dict]:
        """Обнаружение всех видео устройств"""
        devices = []
        
        for i in range(10):  # Проверяем до video9
            device_path = f"/dev/video{i}"
            
            # Проверяем, существует ли устройство
            if not os.path.exists(device_path):
                continue
            
            # Проверяем тип устройства
            try:
                result = subprocess.run(
                    ['v4l2-ctl', '-d', device_path, '--info'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                
                if result.returncode != 0:
                    continue
                
                output = result.stdout
                
                # Проверяем, является ли это устройством видеозахвата
                is_capture = 'Video Capture' in output
                is_output = 'Video Output' in output
                is_overlay = 'Video Overlay' in output
                
                # Получаем информацию о драйвере
                driver_info = self._get_driver_info(device_path)
                
                # Проверяем, не является ли это virtual device
                is_virtual = self._is_virtual_device(driver_info)
                
                devices.append({
                    'device_path': device_path,
                    'is_capture': is_capture,
                    'is_output': is_output,
                    'is_overlay': is_overlay,
                    'driver_info': driver_info,
                    'is_virtual': is_virtual,
                    'is_video_device': True
                })
                
            except:
                continue
        
        return devices
    
    def _filter_real_cameras(self, devices: List[Dict]) -> List[Dict]:
        """Фильтрация реальных камер от виртуальных и дубликатов"""
        real_cameras = []
        processed_bus_info = set()
        
        for device in devices:
            # Пропускаем не устройства захвата
            if not device.get('is_capture', False):
                continue
            
            # Пропускаем виртуальные устройства
            if device.get('is_virtual', False):
                self.logger.debug(f"Пропускаем виртуальное устройство: {device['device_path']}")
                continue
            
            # Получаем уникальный идентификатор камеры (bus info)
            bus_info = self._get_bus_info(device['device_path'])
            
            if not bus_info:
                # Если нет bus info, используем путь к устройству
                device_id = device['device_path']
            else:
                # Используем bus info для группировки
                device_id = bus_info
            
            # Если мы уже видели эту камеру, пропускаем дубликат
            if device_id in processed_bus_info:
                self.logger.debug(f"Пропускаем дубликат камеры: {device['device_path']} ({device_id})")
                continue
            
            processed_bus_info.add(device_id)
            
            # Получаем информацию о камере
            camera_info = self._get_camera_info(device['device_path'])
            
            real_cameras.append({
                'device_path': device['device_path'],
                'name': camera_info.get('name', device['device_path']),
                'formats': camera_info.get('formats', []),
                'resolutions': camera_info.get('resolutions', []),
                'bus_info': bus_info,
                'is_real_camera': True
            })
        
        return real_cameras
    
    def _get_driver_info(self, device_path: str) -> str:
        """Получить информацию о драйвере"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '-D'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Driver name' in line:
                        return line.strip()
        except:
            pass
        return ""
    
    def _is_virtual_device(self, driver_info: str) -> bool:
        """Проверить, является ли устройство виртуальным"""
        virtual_drivers = [
            'v4l2 loopback',
            'uvcvideo',
            'em28xx',  # Некоторые TV тюнеры
            'bttv',    # Другие TV тюнеры
        ]
        
        driver_lower = driver_info.lower()
        for virtual_driver in virtual_drivers:
            if virtual_driver in driver_lower:
                return True
        return False
    
    def _get_bus_info(self, device_path: str) -> str:
        """Получить уникальный идентификатор шины камеры"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--info'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Bus info' in line:
                        return line.split(':')[1].strip()
        except:
            pass
        return ""
    
    def _get_camera_info(self, device_path: str) -> Dict:
        """Получить информацию о камере"""
        try:
            # Получаем название камеры
            name_result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '-D'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            name = device_path
            if name_result.returncode == 0:
                for line in name_result.stdout.split('\n'):
                    if 'Card type' in line or 'Driver name' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            name = parts[1].strip()
                            break
            
            # Получаем форматы
            formats = self._get_simple_formats(device_path)
            
            # Получаем разрешения
            resolutions = self._get_simple_resolutions(device_path)
            
            return {
                'name': name,
                'formats': formats,
                'resolutions': resolutions
            }
            
        except:
            return {
                'name': device_path,
                'formats': [],
                'resolutions': []
            }
    
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
        """Получить простой список разрешений"""
        resolutions = []
        
        # Пробуем получить разрешения для MJPG формата
        try:
            cmd = f"v4l2-ctl -d {device_path} --list-formats-ext 2>/dev/null | grep -A10 'MJPG' | grep 'Size:'"
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
        except:
            pass
        
        # Если не нашли MJPG, пробуем YUYV
        if not resolutions:
            try:
                cmd = f"v4l2-ctl -d {device_path} --list-formats-ext 2>/dev/null | grep -A10 'YUYV' | grep 'Size:'"
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
            except:
                pass
        
        # Удаляем дубликаты и сортируем
        unique_res = list(set(resolutions))
        unique_res.sort(key=lambda x: self._resolution_area(x), reverse=True)
        
        return unique_res[:3]  # Возвращаем только 3 самых больших разрешения
    
    def _resolution_area(self, resolution: str) -> int:
        """Вычислить площадь разрешения для сортировки"""
        try:
            w, h = map(int, resolution.split('x'))
            return w * h
        except:
            return 0