#!/usr/bin/env python3
"""
Модуль для детектирования и анализа камер с использованием v4l2-ctl
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional, Tuple

class CameraDetector:
    """Класс для детектирования и анализа камер"""
    
    def __init__(self):
        self.logger = logging.getLogger('flask_stream')
    
    def get_device_info(self, device_path: str) -> Dict:
        """Получение информации об устройстве через v4l2-ctl --info"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {'error': f"Не удалось получить информацию: {result.stderr}"}
            
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            return info
            
        except subprocess.TimeoutExpired:
            return {'error': 'Таймаут при получении информации'}
        except Exception as e:
            return {'error': f"Ошибка: {str(e)}"}
    
    def get_formats(self, device_path: str) -> List[Dict]:
        """Получение списка форматов камеры"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--list-formats-ext'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return []
            
            formats = []
            current_format = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                # Начало нового формата
                if line.startswith('[') and ']:':
                    if current_format:
                        formats.append(current_format)
                    
                    # Извлекаем ID и имя формата
                    match = re.match(r'\[(\d+)\]:\s*\'(.+)\'', line)
                    if match:
                        current_format = {
                            'index': int(match.group(1)),
                            'name': match.group(2),
                            'description': '',
                            'sizes': []
                        }
                
                # Описание формата
                elif line.startswith('Name') and current_format:
                    current_format['description'] = line.split(':', 1)[1].strip()
                
                # Размеры для формата
                elif line.startswith('Size') and current_format:
                    size_match = re.search(r'Size: Discrete (\d+)x(\d+)', line)
                    if size_match:
                        width, height = int(size_match.group(1)), int(size_match.group(2))
                        
                        # Получаем FPS для этого размера
                        fps_list = self._parse_fps_from_size_block(result.stdout, line)
                        
                        current_format['sizes'].append({
                            'width': width,
                            'height': height,
                            'fps': fps_list
                        })
            
            if current_format:
                formats.append(current_format)
            
            return formats
            
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Таймаут при получении форматов для {device_path}")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка получения форматов для {device_path}: {e}")
            return []
    
    def _parse_fps_from_size_block(self, output: str, size_line: str) -> List[int]:
        """Парсинг FPS из блока размера"""
        try:
            lines = output.split('\n')
            size_index = lines.index(size_line)
            
            fps_values = []
            for i in range(size_index + 1, min(size_index + 20, len(lines))):
                line = lines[i].strip()
                if line.startswith('Interval'):
                    fps_match = re.search(r'(\d+\.\d+) fps', line)
                    if fps_match:
                        fps = round(float(fps_match.group(1)))
                        if fps not in fps_values:
                            fps_values.append(fps)
                elif line.startswith('Size') or line.startswith('['):
                    break
            
            return sorted(fps_values)
        except:
            return []
    
    def is_video_capture_device(self, device_path: str) -> bool:
        """Проверка, является ли устройство видеозахватом (не метаданными)"""
        try:
            # Используем тот же подход, что и в check_cam_formats.sh
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '--info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False
            
            # Проверяем, содержит ли вывод "Video Capture"
            output = result.stdout.lower()
            if 'video capture' in output:
                # Дополнительная проверка: убедимся, что это не чистое устройство метаданных
                if 'metadata capture' in output and 'video capture' not in output:
                    return False
                return True
            
            return False
            
        except Exception:
            return False
    
    def detect_cameras(self, max_devices: int = 10) -> List[Dict]:
        """Обнаружение всех видеокамер в системе"""
        cameras = []
        
        for i in range(max_devices):
            device_path = f"/dev/video{i}"
            
            # Проверяем, существует ли устройство
            try:
                device_info = self.get_device_info(device_path)
                
                if 'error' in device_info:
                    continue
                
                # Проверяем, является ли это видеоустройством
                if not self.is_video_capture_device(device_path):
                    self.logger.debug(f"{device_path} - не видеоустройство (метаданные или другое)")
                    continue
                
                # Получаем форматы
                formats = self.get_formats(device_path)
                
                camera_info = {
                    'device_path': device_path,
                    'device_id': i,
                    'card_type': device_info.get('Card type', 'Unknown'),
                    'driver': device_info.get('Driver name', 'Unknown'),
                    'bus_info': device_info.get('Bus info', 'Unknown'),
                    'capabilities': device_info.get('Capabilities', ''),
                    'formats': formats,
                    'supported_resolutions': self._get_supported_resolutions(formats),
                    'supported_fps': self._get_supported_fps(formats)
                }
                
                cameras.append(camera_info)
                self.logger.info(f"✅ {device_path} - Видеокамера найдена: {camera_info['card_type']}")
                
            except Exception as e:
                self.logger.debug(f"{device_path} - Ошибка: {e}")
                continue
        
        return cameras
    
    def _get_supported_resolutions(self, formats: List[Dict]) -> List[str]:
        """Получение списка поддерживаемых разрешений"""
        resolutions = set()
        for fmt in formats:
            for size in fmt.get('sizes', []):
                resolutions.add(f"{size['width']}x{size['height']}")
        return sorted(list(resolutions))
    
    def _get_supported_fps(self, formats: List[Dict]) -> List[int]:
        """Получение списка поддерживаемых FPS"""
        fps_values = set()
        for fmt in formats:
            for size in fmt.get('sizes', []):
                fps_values.update(size.get('fps', []))
        return sorted(list(fps_values))
    
    def get_best_resolution_for_fps(self, formats: List[Dict], target_fps: int) -> Optional[Tuple[int, int]]:
        """Получение наилучшего разрешения для заданного FPS"""
        best_resolution = None
        best_pixels = 0
        
        for fmt in formats:
            for size in fmt.get('sizes', []):
                if target_fps in size.get('fps', []):
                    pixels = size['width'] * size['height']
                    if pixels > best_pixels:
                        best_pixels = pixels
                        best_resolution = (size['width'], size['height'])
        
        return best_resolution
    
    def log_camera_detection_results(self, cameras: List[Dict]):
        """Логирование результатов детектирования камер"""
        self.logger.info("=" * 70)
        self.logger.info("🔍 РЕЗУЛЬТАТЫ ДЕТЕКТИРОВАНИЯ КАМЕР")
        self.logger.info("=" * 70)
        
        if not cameras:
            self.logger.warning("❌ Видеокамеры не найдены в системе")
            return
        
        self.logger.info(f"📊 Найдено видеокамер: {len(cameras)}")
        
        for i, cam in enumerate(cameras, 1):
            self.logger.info(f"")
            self.logger.info(f"📹 КАМЕРА {i}: {cam['device_path']}")
            self.logger.info(f"   🏷️  Тип: {cam['card_type']}")
            self.logger.info(f"   🚀 Драйвер: {cam['driver']}")
            self.logger.info(f"   🚌 Шина: {cam['bus_info']}")
            self.logger.info(f"   📋 Поддерживаемые разрешения: {', '.join(cam['supported_resolutions'])}")
            self.logger.info(f"   📊 Поддерживаемые FPS: {', '.join(map(str, cam['supported_fps']))}")
            
            # Логируем форматы
            if cam['formats']:
                self.logger.info(f"   📴 Форматы:")
                for fmt in cam['formats']:
                    sizes_str = ', '.join([f"{s['width']}x{s['height']}" for s in fmt['sizes']])
                    self.logger.info(f"      - {fmt['name']} ({fmt['description']}): {sizes_str}")
        
        self.logger.info("=" * 70)

def detect_cameras(max_devices: int = 10) -> List[Dict]:
    """Функция для быстрого детектирования камер"""
    detector = CameraDetector()
    cameras = detector.detect_cameras(max_devices)
    detector.log_camera_detection_results(cameras)
    return cameras