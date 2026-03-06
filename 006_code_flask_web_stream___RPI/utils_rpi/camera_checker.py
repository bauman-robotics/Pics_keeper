#!/usr/bin/env python3

# camera_checker.py 

"""
Улучшенный детектор камер с полной информацией о разрешениях и FPS
С добавлением кэширования для ускорения работы в Flask
"""
import sys
import subprocess
import re
import logging
import time
from typing import List, Dict

#, Optional, Tuple

class CameraChecker:
    """Класс для проверки камер на основе v4l2-ctl с кэшированием"""

    def __init__(self, logger=None, log_level=logging.INFO):
        # Используем переданный логгер или создаем новый
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('flask_stream')
            self.logger.setLevel(log_level)
        
            # Если нет хендлеров, добавляем консольный
            if not self.logger.handlers:
                handler = logging.StreamHandler(sys.stdout)
                handler.setLevel(log_level)
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

        self.camera_names = self._get_camera_names()
        
        # Кэширование для ускорения
        self.camera_cache = {}
        self.cache_time = {}
        self.CACHE_TTL = 30  # Кэшировать на 30 секунд
    
    def check_device(self, device_path: str) -> Dict:
        """Проверка устройства на наличие видеозахвата (с кэшированием)"""
        current_time = time.time()
        
        # Проверяем кэш
        if (device_path in self.camera_cache and 
            device_path in self.cache_time and
            current_time - self.cache_time[device_path] < self.CACHE_TTL):
            return self.camera_cache[device_path]
        
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
                            match = re.search(r"'([^']+)'", line)
                            if match:
                                formats.append(match.group(1))
                
                # Получаем полную информацию о разрешениях и FPS
                resolutions_info = self._get_full_resolution_info(device_path)
                
                # Считаем устройство видеокамерой только если есть форматы
                if formats:
                    result = {
                        'device_path': device_path,
                        'type': 'Video Capture',
                        'formats': formats,
                        'resolutions_info': resolutions_info,
                        'success': True
                    }
                    
                    # Сохраняем в кэш
                    self.camera_cache[device_path] = result
                    self.cache_time[device_path] = current_time
                    
                    return result
                else:
                    result = {
                        'device_path': device_path,
                        'type': 'Other',
                        'formats': [],
                        'resolutions_info': {},
                        'success': False
                    }
                    
                    self.camera_cache[device_path] = result
                    self.cache_time[device_path] = current_time
                    
                    return result
            else:
                result = {
                    'device_path': device_path,
                    'type': 'Other',
                    'formats': [],
                    'resolutions_info': {},
                    'success': False
                }
                
                self.camera_cache[device_path] = result
                self.cache_time[device_path] = current_time
                
                return result
                
        except Exception as e:
            return {'error': f"Ошибка при проверке {device_path}: {str(e)}"}
    
    def detect_cameras(self, max_devices: int = 40) -> List[Dict]:
        """Обнаружение видеокамер (ускоренная версия)"""
        cameras = []
        video_devices = self._find_video_devices(max_devices)
        
        if not video_devices:
            return []
        
        # Проверяем каждое устройство
        for device_path in video_devices:
            self.logger.info(f"🔍 Проверка устройства {device_path}")
            
            result = self.check_device(device_path)
            
            if 'error' in result:
                self.logger.error(f"{device_path} - Ошибка: {result['error']}")
                continue
            
            if result['success']:
                cameras.append(result)
        
        return cameras
    
    def _find_video_devices(self, max_devices: int) -> List[str]:
        """Быстрое нахождение видео устройств"""
        import glob
        import os
        
        devices = []
        
        # Используем glob для быстрого поиска
        video_devices = glob.glob('/dev/video*')
        
        # Сортируем численно (/dev/video0, /dev/video1 и т.д.)
        def video_sort_key(path):
            try:
                return int(path.replace('/dev/video', ''))
            except:
                return 999
        
        video_devices.sort(key=video_sort_key)
        
        # Берем только первые max_devices
        for device in video_devices[:max_devices]:
            # Быстрая проверка существования
            if os.path.exists(device):
                devices.append(device)
        
        return devices
    
    def detect_cameras_fast(self, max_devices: int = 5) -> List[Dict]:
            """Быстрое обнаружение камер (только основные)"""
            cameras = []
            video_devices = self._find_video_devices(max_devices)
            
            for device_path in video_devices:
                try:
                    # Быстрая проверка - пытаемся открыть
                    with open(device_path, 'rb'):
                        pass
                    
                    # Проверяем кэш
                    current_time = time.time()
                    if (device_path in self.camera_cache and 
                        device_path in self.cache_time and
                        current_time - self.cache_time[device_path] < self.CACHE_TTL):
                        
                        result = self.camera_cache[device_path]
                        if result.get('success', False):
                            cameras.append(result)
                            continue
                    
                    # Если нет в кэше или устарел, проверяем быстро
                    result = subprocess.run(
                        ['v4l2-ctl', '-d', device_path, '--info'],
                        capture_output=True,
                        text=True,
                        timeout=2  # Уменьшенный таймаут
                    )
                    
                    if result.returncode == 0 and 'Video Capture' in result.stdout:
                        # Базовая информация о камере
                        camera_info = {
                            'device_path': device_path,
                            'name': self._get_camera_name_fast(device_path),
                            'formats': ['MJPG', 'YUYV'],  # Предполагаем стандартные
                            'resolutions': ['640x480', '320x240'],  # Базовые разрешения
                            'success': True
                        }
                        
                        # Сохраняем в кэш
                        self.camera_cache[device_path] = camera_info
                        self.cache_time[device_path] = time.time()
                        
                        cameras.append(camera_info)
                        
                except Exception as e:
                    self.logger.info(f"Пропуск {device_path}: {e}")
                    continue
            
            return cameras
        
    def log_detection_results_with_fps(self, cameras: List[Dict]):
        """Логирование результатов с полной информацией о FPS"""
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
            
            # Форматы
            formats_str = ', '.join(cam['formats'])
            self.logger.info(f"   📴 Форматы: {formats_str}")
            
            # Разрешения с FPS
            self.logger.info(f"   📋 Разрешения:")
            
            # Получаем все уникальные разрешения из всех форматов
            all_resolutions = self._get_all_resolutions_sorted(cam['resolutions_info'])
            
            for resolution in all_resolutions[:10]:  # Показываем первые 10 разрешений
                fps_by_format = self._get_fps_for_resolution(cam['resolutions_info'], resolution)
                if fps_by_format:
                    # Форматируем строку с FPS
                    fps_str = self._format_fps_string(fps_by_format)
                    self.logger.info(f"      • {resolution}: {fps_str}")
            
            # Если разрешений много, показываем статистику
            total_resolutions = len(all_resolutions)
            if total_resolutions > 10:
                self.logger.info(f"      ... и ещё {total_resolutions - 10} разрешений")
            
            self.logger.info(f"   📈 Итого: {len(cam['formats'])} форматов, {total_resolutions} разрешений")
        
        self.logger.info("=" * 80)
    
    def _get_camera_names(self) -> Dict[str, str]:
        """Получение названий камер по устройствам"""
        cameras = {}
        try:
            result = subprocess.run(['v4l2-ctl', '--list-devices'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                current_camera = None
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('\t'):
                        current_camera = line.strip()
                    elif line.strip() and line.startswith('\t'):
                        device_match = re.search(r'/dev/video\d+', line)
                        if device_match and current_camera:
                            device = device_match.group()
                            cameras[device] = current_camera
        except Exception as e:
            self.logger.error(f"Ошибка при получении названий камер: {e}")
        
        return cameras
    
    def _get_camera_name(self, device_path: str) -> str:
        """Получение названия камеры по устройству"""
        return self.camera_names.get(device_path, "Неизвестная камера")
    
    def _get_camera_name_fast(self, device_path: str) -> str:
        """Быстрое получение названия камеры"""
        # Пробуем получить из кэша
        if device_path in self.camera_names:
            return self.camera_names[device_path]
        
        # Или используем простой вариант
        try:
            result = subprocess.run(
                ['v4l2-ctl', '-d', device_path, '-D'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Card type' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            return parts[1].strip()
        except:
            pass
        
        return device_path
    
    def _get_full_resolution_info(self, device_path: str) -> Dict[str, Dict[str, List[float]]]:
        """
        Получить полную информацию о разрешениях и FPS для всех форматов
        
        Возвращает:
            {
                'YUYV': {
                    '640x480': [30.0, 25.0, 20.0, ...],
                    '1280x720': [10.0, 5.0]
                },
                'MJPG': {
                    '640x480': [30.0, 25.0, 20.0, ...],
                    '1280x720': [30.0, 25.0, ...]
                }
            }
        """
        result = {}
        
        try:
            cmd = f"v4l2-ctl -d {device_path} --list-formats-ext"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=5)
            
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
                    fps = float(fps_match.group(1))
                    if fps not in result[current_format][current_resolution]:
                        result[current_format][current_resolution].append(fps)
            
            # Сортируем FPS по убыванию для каждого разрешения
            for fmt in result:
                for res in result[fmt]:
                    result[fmt][res].sort(reverse=True)
                    
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Ошибка получения FPS для {device_path}: {e}")
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка для {device_path}: {e}")
        
        return result
    
    def _get_all_resolutions_sorted(self, resolutions_info: Dict) -> List[str]:
        """Получить все уникальные разрешения, отсортированные по площади"""
        all_resolutions = set()
        
        for fmt, resolutions in resolutions_info.items():
            all_resolutions.update(resolutions.keys())
        
        # Сортируем по площади (ширина * высота)
        return sorted(
            all_resolutions,
            key=lambda res: self._calculate_resolution_area(res),
            reverse=True
        )
    
    def _get_fps_for_resolution(self, resolutions_info: Dict, resolution: str) -> Dict[str, List[float]]:
        """Получить FPS для конкретного разрешения по всем форматам"""
        fps_by_format = {}
        
        for fmt, resolutions in resolutions_info.items():
            if resolution in resolutions:
                fps_by_format[fmt] = resolutions[resolution]
        
        return fps_by_format
    
    def _format_fps_string(self, fps_by_format: Dict[str, List[float]]) -> str:
        """Форматировать строку с FPS для вывода"""
        parts = []
        
        for fmt, fps_list in fps_by_format.items():
            if len(fps_list) <= 3:
                fps_str = '/'.join([f"{fps:.1f}" for fps in fps_list])
            else:
                top_fps = '/'.join([f"{fps:.1f}" for fps in fps_list[:3]])
                fps_str = f"{top_fps}..."
            
            parts.append(f"{fmt}:{fps_str}fps")
        
        return ', '.join(parts)
    
    def _calculate_resolution_area(self, resolution: str) -> int:
        """Рассчитывает площадь разрешения для сортировки"""
        try:
            width, height = map(int, resolution.split('x'))
            return width * height
        except (ValueError, TypeError):
            return 0
    
    def get_simplified_info(self, device_path: str) -> Dict:
        """Получить упрощенную информацию для быстрого выбора"""
        info = self.check_device(device_path)
        if not info.get('success'):
            return {}
        
        result = {
            'device': device_path,
            'name': self._get_camera_name(device_path),
            'formats': info['formats'],
            'best_resolutions': []
        }
        
        # Находим лучшие комбинации (макс FPS для каждого разрешения)
        resolutions_info = info['resolutions_info']
        
        # Для каждого формата собираем лучшие FPS
        best_by_format = {}
        for fmt, resolutions in resolutions_info.items():
            for res, fps_list in resolutions.items():
                if fps_list:
                    max_fps = max(fps_list)
                    if res not in best_by_format or max_fps > best_by_format[res]['fps']:
                        best_by_format[res] = {
                            'resolution': res,
                            'format': fmt,
                            'fps': max_fps
                        }
        
        # Сортируем по разрешению
        sorted_resolutions = sorted(
            best_by_format.values(),
            key=lambda x: self._calculate_resolution_area(x['resolution']),
            reverse=True
        )
        
        result['best_resolutions'] = sorted_resolutions[:5]  # Топ 5
        return result
    
    def get_cameras_for_api(self) -> List[Dict]:
        """Получить список камер для API (быстро, с фильтрацией)"""
        current_time = time.time()
        
        # Проверяем кэш для списка камер
        if (hasattr(self, '_api_cache') and 
            hasattr(self, '_api_cache_time') and
            current_time - self._api_cache_time < self.CACHE_TTL):
            return self._api_cache
        
        # Получаем камеры
        cameras = self.detect_cameras_fast(max_devices=8)
        
        # Фильтруем только успешные камеры
        real_cameras = [cam for cam in cameras if cam.get('success', False)]
        
        # Группируем по имени (чтобы убрать дубликаты одной камеры)
        unique_cameras = []
        seen_names = set()
        
        for cam in real_cameras:
            name = self._get_camera_name(cam['device_path'])
            
            # Если это новая камера (по имени) или у нас ещё нет камер
            if name not in seen_names or not seen_names:
                seen_names.add(name)
                
                # ПРОВЕРЯЕМ: если это CSI камера - пропускаем (она будет добавлена отдельно в endpoint)
                if self._is_csi_camera_by_name(name):
                    print(f"🔄 Пропускаем CSI камеру в USB списке: {name}")
                    continue
                
                # Упрощаем данные для API
                api_cam = {
                    'device_path': cam['device_path'],
                    'name': name,
                    'formats': cam.get('formats', [])[:3],  # Максимум 3 формата
                    'resolutions': self._extract_resolutions_simple(cam),
                    'is_camera': True
                }
                
                unique_cameras.append(api_cam)
        
        # Сохраняем в кэш
        self._api_cache = unique_cameras
        self._api_cache_time = current_time
        
        return unique_cameras
    
    def _is_csi_camera_by_name(self, name: str) -> bool:
        """Определяет по названию, является ли камера CSI"""
        if not name:
            return False
        
        name_lower = name.lower()
        
        # Признаки CSI камер Raspberry Pi
        csi_indicators = [
            'csi',            # CSI в названии
            'rp1-cfe',        # Raspberry Pi Camera Foundation
            'platform:',      # platform: в названии (для RPi)
            'bcm2835',        # Broadcom CSI
            'imx',           # Sony IMX датчики (часто CSI)
            'ov',            # OmniVision датчики
            'arducam',       # Arducam модули (часто CSI)
            'picamera',      # Raspberry Pi Camera
            'raspberry',     # Raspberry Pi
        ]
        
        for indicator in csi_indicators:
            if indicator in name_lower:
                return True
        
        return False

    def _extract_resolutions_simple(self, camera_info: Dict) -> List[str]:
        """Извлечь упрощенный список разрешений"""
        resolutions_info = camera_info.get('resolutions_info', {})
        
        if not resolutions_info:
            return ['640x480', '320x240']  # Стандартные разрешения
        
        # Собираем все уникальные разрешения
        all_resolutions = set()
        for fmt, resolutions in resolutions_info.items():
            all_resolutions.update(resolutions.keys())
        
        # Сортируем по размеру и берем топ-5
        sorted_res = sorted(
            all_resolutions,
            key=lambda res: self._calculate_resolution_area(res),
            reverse=True
        )
        
        return sorted_res[:5]

def check_cameras_with_fps(max_devices: int = 10) -> List[Dict]:
    """Функция для проверки камер с выводом FPS"""    

    # Настраиваем логгер для консоли
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    checker = CameraChecker()
    cameras = checker.detect_cameras(max_devices)
    checker.log_detection_results_with_fps(cameras)
    
    return cameras

def get_recommended_settings(cameras: List[Dict]) -> List[Dict]:
    """Получить рекомендованные настройки для каждой камеры"""
    recommendations = []
    
    for cam in cameras:
        device_path = cam['device_path']
        
        # Для каждого формата ищем лучшее сочетание разрешения и FPS
        best_settings = []
        resolutions_info = cam['resolutions_info']
        
        for fmt, resolutions in resolutions_info.items():
            # Находим разрешение с максимальной площадью и высоким FPS
            if resolutions:
                # Сортируем разрешения по площади
                sorted_res = sorted(
                    resolutions.keys(),
                    key=lambda res: CameraChecker()._calculate_resolution_area(res),
                    reverse=True
                )
                
                # Берем топ-3 разрешения
                for res in sorted_res[:3]:
                    fps_list = resolutions[res]
                    if fps_list:
                        max_fps = max(fps_list)
                        best_settings.append({
                            'format': fmt,
                            'resolution': res,
                            'max_fps': max_fps,
                            'all_fps': fps_list
                        })
        
        # Сортируем по приоритету: сначала по разрешению, потом по FPS
        best_settings.sort(
            key=lambda x: (
                CameraChecker()._calculate_resolution_area(x['resolution']),
                x['max_fps']
            ),
            reverse=True
        )
        
        recommendations.append({
            'device': device_path,
            'name': CameraChecker()._get_camera_name(device_path),
            'recommended': best_settings[:3] if best_settings else []
        })
    
    return recommendations

def main():
    """Тестовая функция с полной информацией"""
    print("🔍 Тестирование детектора камер с полной информацией о FPS")
    print("=" * 80)
    
    try:
        cameras = check_cameras_with_fps(max_devices=10)
        
        if cameras:
            print("\n" + "=" * 80)
            print("🎯 РЕКОМЕНДОВАННЫЕ НАСТРОЙКИ ДЛЯ КАМЕР:")
            print("=" * 80)
            
            recommendations = get_recommended_settings(cameras)
            
            for i, rec in enumerate(recommendations, 1):
                print(f"\n📹 КАМЕРА {i}: {rec['device']}")
                print(f"   Название: {rec['name']}")
                
                if rec['recommended']:
                    print(f"   🏆 Лучшие настройки:")
                    for j, setting in enumerate(rec['recommended'], 1):
                        print(f"      {j}. {setting['format']} - {setting['resolution']} @ {setting['max_fps']:.1f}fps")
                        if len(setting['all_fps']) > 1:
                            other_fps = [f"{fps:.1f}" for fps in setting['all_fps'] if fps != setting['max_fps']]
                            print(f"         Также доступно: {', '.join(other_fps)}fps")
                else:
                    print(f"   ⚠️ Рекомендации не найдены")
        
        print("\n" + "=" * 80)
        print("✅ Тестирование завершено")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':    
    main()