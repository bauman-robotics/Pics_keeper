#!/usr/bin/env python3
"""
Улучшенный детектор камер с полной информацией о разрешениях и FPS
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional, Tuple

class CameraChecker:
    """Класс для проверки камер на основе v4l2-ctl"""
    
    def __init__(self, log_level=logging.INFO):
        self.logger = logging.getLogger('flask_stream')
        self.logger.setLevel(log_level)
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
                            match = re.search(r"'([^']+)'", line)
                            if match:
                                formats.append(match.group(1))
                
                # Получаем полную информацию о разрешениях и FPS
                resolutions_info = self._get_full_resolution_info(device_path)
                
                # Считаем устройство видеокамерой только если есть форматы
                if formats:
                    return {
                        'device_path': device_path,
                        'type': 'Video Capture',
                        'formats': formats,
                        'resolutions_info': resolutions_info,
                        'success': True
                    }
                else:
                    return {
                        'device_path': device_path,
                        'type': 'Other',
                        'formats': [],
                        'resolutions_info': {},
                        'success': False
                    }
            else:
                return {
                    'device_path': device_path,
                    'type': 'Other',
                    'formats': [],
                    'resolutions_info': {},
                    'success': False
                }
                
        except Exception as e:
            return {'error': f"Ошибка при проверке {device_path}: {str(e)}"}
    
    def detect_cameras(self, max_devices: int = 10) -> List[Dict]:
        """Обнаружение видеокамер"""
        cameras = []
        
        for i in range(max_devices):
            device_path = f"/dev/video{i}"
            
            # Проверяем, существует ли устройство
            try:
                with open(device_path, 'r'):
                    pass
            except (FileNotFoundError, PermissionError):
                continue
            
            self.logger.debug(f"🔍 Проверка устройства {device_path}")
            
            result = self.check_device(device_path)
            
            if 'error' in result:
                self.logger.debug(f"{device_path} - Ошибка: {result['error']}")
                continue
            
            if result['success']:
                cameras.append(result)
        
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
            self.logger.info(f"   📋 Разрешения и доступные FPS:")
            
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
            self.logger.debug(f"Ошибка при получении названий камер: {e}")
        
        return cameras
    
    def _get_camera_name(self, device_path: str) -> str:
        """Получение названия камеры по устройству"""
        return self.camera_names.get(device_path, "Неизвестная камера")
    
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
                    fps = float(fps_match.group(1))
                    if fps not in result[current_format][current_resolution]:
                        result[current_format][current_resolution].append(fps)
            
            # Сортируем FPS по убыванию для каждого разрешения
            for fmt in result:
                for res in result[fmt]:
                    result[fmt][res].sort(reverse=True)
                    
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Ошибка получения FPS для {device_path}: {e}")
        except Exception as e:
            self.logger.debug(f"Неожиданная ошибка для {device_path}: {e}")
        
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

def check_cameras_with_fps(max_devices: int = 10) -> List[Dict]:
    """Функция для проверки камер с выводом FPS"""
    import sys
    
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