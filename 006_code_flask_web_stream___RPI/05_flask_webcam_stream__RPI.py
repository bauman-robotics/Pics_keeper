#!/usr/bin/env python3
"""
Flask Web Server for Webcam Streaming - Version 4
YAML Configuration Support

name: 
05_flask_webcam_stream__RPI.py
old name: 
02_flask_webcam_stream.py
"""

'''
export DISPLAY=:0

1. убить сессию:
screen -X -S bird_detector quit

2. активация вирт окружения
source /home/pi/projects/Hailo8_projects/Hailo-8/16__hailort_v4.23.0/hailo_runtime_env/bin/activate

3. 
export DISPLAY=:0 && python3 /home/pi/projects/Hailo8_projects/Hailo-8/17_Bird_Detector/bird_detector_v5_5.py --input rpi

4.
export DISPLAY=:0 && python3 /home/pi/projects/Hailo8_projects/Hailo-8/17_Bird_Detector/bird_detector_v5_6_test_v4.py --input rpi

5.
export DISPLAY=:0 && python3 /home/pi/projects/Hailo8_projects/Hailo-8/17_Bird_Detector/bird_detector_v5_7_cat.py --input rpi


6. Выбор камер и fps 
export DISPLAY=:0 && python3 /home/pi/projects/Hailo8_projects/Hailo-8/20_imx415_cam/hailo_inference/bird_detector_v5_5_fps.py --input rpi

sudo lsof /dev/video* 2>/dev/null || echo "Камеры свободны"

# Посмотрите устройства V4L2
v4l2-ctl --list-devices

deactivate

=== WEB only ==== flask ======
Скрипт для стрима с выбранной веб камеры + выбор, запуск и остановка на веб странице. На flask.  
Папка: 004_code_flask_web_stream
03_flask_webcam_stream__RPI.py
+ config_rpi.yaml

+ остановил pipiwire  
- Не работает на распберри. 

http://localhost:5000/api/cameras
=================

pip install picamera2 numpy opencv-python

==== pi venv ==== 
source /home/pi/projects/Hailo8_projects/cam_calibr/venv/bin/activate

cd 006_code_flask_web_stream___RPI

deactivate 

http://192.168.31.56:5000/

=== pc venv ====
source /home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/venv/bin/activate

cd /home/ypc/projects/Hailo-8_projects/04_Pics_keeper/Pics_keeper/006_code_flask_web_stream___RPI

cd 006_code_flask_web_stream___RPI

python3 05_flask_webcam_stream__RPI.py

sudo lsof -i :5000

http://localhost:5000/


'''


import yaml
import cv2
import sys
import threading
import time
import queue
import copy
import os
import numpy as np
from flask import Flask, Response, render_template, jsonify, request
import argparse
from utils_rpi.camera_checker import CameraChecker
from utils_rpi.test_cam_backend import test_camera_backends
from datetime import datetime

# Импортируем логгер
from utils_rpi.logger import create_logger

# Добавляем путь к utils_rpi
current_dir = os.path.dirname(os.path.abspath(__file__))
utils_path = os.path.join(current_dir, 'utils_rpi')
if utils_path not in sys.path:
    sys.path.append(utils_path)

# Пробуем импортировать CSI Camera Manager
try:
    from utils_rpi.csi_camera_manager import CSICameraManager
    PICAMERA2_AVAILABLE = True

except ImportError as e:
    print(f"⚠️  Не удалось загрузить CSICameraManager: {e}")    
    print("   Установите: pip install picamera2")
    print("   Или проверьте наличие файла utils_rpi/csi_camera_manager.py")
    PICAMERA2_AVAILABLE = False
    CSICameraManager = None

try:
    from picamera2 import Picamera2    
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("⚠️  Picamera2 не установлен. CSI камеры не будут доступны.")
    print("   Установите: pip install picamera2")


def load_config(config_path="config_rpi.yaml"):
    """Загрузка конфигурации из YAML файла"""
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            print(f"✅ Конфигурация загружена из {config_path}")
            return config
    except FileNotFoundError:
        print(f"❌ Файл конфигурации не найден: {config_path}")
        print("Используйте --config для указания пути к конфигурационному файлу")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Ошибка парсинга YAML: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

class CameraStreamer:
    """Класс для управления камерой и стримингом"""
    
    def __init__(self, config, logger, camera_info):
        self.config = config
        self.logger = logger
        
        # # Инициализируем менеджер CSI камер
        # self.csi_manager = CSICameraManager(config, logger)
        
        # # Определяем тип текущей камеры
        # if camera_info['type'] == 'csi':
        #     self.camera_type = 'csi'            
        #     self.current_picam2 = camera_info.get('picam2')
        #     self.csi_manager.current_picam2 = self.current_picam2
        #     self.csi_manager.current_camera = camera_info.get('csi_manager', {}).current_camera
        #     self.current_v4l2_camera = None
        # else:
        #     self.camera_type = 'v4l2'
        #     self.current_v4l2_camera = camera_info.get('camera')
        #     self.current_picam2 = None

        # ===== ВАЖНО: ИНИЦИАЛИЗИРУЕМ csi_settings =====
        self.csi_settings = {}  # ← ЭТО ЕСТЬ!

        # Определяем тип текущей камеры
        if camera_info['type'] == 'csi':
            self.camera_type = 'csi'
            # Используем существующий csi_manager из camera_info
            self.csi_manager = camera_info.get('csi_manager')
            self.current_picam2 = camera_info.get('picam2')
            self.current_v4l2_camera = None
            self.current_camera_idx = camera_info.get('camera_idx', 0)
            
            print(f"✅ CSI камера инициализирована: индекс {self.current_camera_idx}")

            # ===== ВАЖНО: ЗАГРУЖАЕМ НАСТРОЙКИ =====
            self._load_csi_settings()
            
            # Проверим, что загрузилось
            if self.csi_settings:
                print(f"📋 Загружены настройки для {self.csi_settings.get('name', 'CSI camera')}")
                print(f"   Режим фокуса: {self.csi_settings.get('af_mode', 'unknown')}")
                print(f"   Позиция линзы: {self.csi_settings.get('lens_position', 0.0)}")

        else:
            self.camera_type = 'v4l2'
            self.current_v4l2_camera = camera_info.get('camera')
            self.current_picam2 = None
            self.csi_manager = None            

        # Состояние стрима
        self.stream_active = False
        self.buffer_active = False
        self.frame_count = 0
        
        # Буферизация
        self.frame_buffer = queue.Queue(maxsize=30)
        self.camera_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.last_frame = None
        self.buffer_thread = None
        
        # Управление подключениями
        self.active_streams = 0
        self.MAX_CONCURRENT_STREAMS = config['server'].get('max_concurrent_streams', 4)
        self.stream_lock = threading.Lock()
        
        # Словарь для отслеживания активных соединений
        self.active_clients = {}
        self.MAX_STREAMS_PER_CLIENT = 1
        
        # Определяем путь к шаблонам
        templates_folder = config.get('paths', {}).get('templates_folder', 'templates')
        
        # Полный путь к шаблонам
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_templates_path = os.path.join(current_dir, templates_folder)

        # Убедиться, что папки существуют
        self.photos_dir = os.path.join(current_dir, 'static', 'photos')
        os.makedirs(self.photos_dir, exist_ok=True)
        
        # Проверяем существование папки
        if not os.path.exists(full_templates_path):
            print(f"⚠️  Папка шаблонов не найдена: {full_templates_path}")
            print(f"   Создаю папку {full_templates_path}")
            os.makedirs(full_templates_path, exist_ok=True)
            
            # Создаем простой index.html если его нет
            index_path = os.path.join(full_templates_path, 'index.html')
            if not os.path.exists(index_path):
                with open(index_path, 'w') as f:
                    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Webcam Stream</title>
</head>
<body>
    <h1>🎥 Webcam Stream</h1>
    <div id="status">Сервер работает!</div>
    <a href="/status">Статус</a> | 
    <a href="/logs">Логи</a>
</body>
</html>''')
        
        print(f"📁 Папка шаблонов: {full_templates_path}")
        
        # Инициализация Flask с абсолютным путем
        self.app = Flask(__name__, template_folder=full_templates_path)
        
        # Настройка маршрутов
        self.setup_routes()
        
        # Сканируем доступные камеры
        try:
            self.camera_checker = CameraChecker(logger=self.logger)
            self.available_cameras = self.camera_checker.detect_cameras()
        except Exception as e:
            print(f"⚠️  Ошибка сканирования камер: {e}")
            self.available_cameras = []
        
        # Добавляем отслеживание времени активности стримов
        self.stream_sessions = {}  # client_id -> timestamp
        
        # Таймер для очистки старых стримов
        self.cleanup_timer = threading.Timer(30.0, self.cleanup_old_streams)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
        
        print(f"✅ CameraStreamer инициализирован")

        # Кэш для списка камер
        self.cameras_cache = None
        self.cameras_cache_time = 0
        self.CAMERAS_CACHE_TTL = 30  # секунд


    def _load_csi_settings(self):
        """Загружает настройки для конкретной CSI камеры"""
        
        # Определяем индекс текущей CSI камеры
        device = self.config['camera'].get('device', 'csi_0')
        camera_idx = device.split('_')[1] if '_' in device else '0'
        camera_key = f"csi_{camera_idx}"
        
        # Получаем настройки для этой камеры из секции csi_cameras
        csi_config = self.config.get('csi_cameras', {}).get(camera_key, {})
        
        print(f"\n📷 ЗАГРУЗКА НАСТРОЕК ДЛЯ {camera_key}: {csi_config.get('name', 'Unknown')}")
        print("="*60)
        
        # СОЗДАЕМ СЛОВАРЬ
        settings = {
            # Основные
            'name': csi_config.get('name', f'CSI Camera {camera_idx}'),
            'width': csi_config.get('width', 1920),
            'height': csi_config.get('height', 1080),
            'fps': csi_config.get('fps', 30),
        }
        
        # Добавляем настройки в зависимости от типа камеры
        if camera_key == 'csi_0':  # IMX708
            print("🎯 Обнаружена IMX708 (с автофокусом)")
            settings.update({
                'af_mode': csi_config.get('af_mode', 'auto'),  # auto, а не continuous
                'lens_position': csi_config.get('lens_position', 0.0),
                'af_window': csi_config.get('af_window', False),
                'af_window_size': csi_config.get('af_window_size', 0.3),
                'ae_mode': csi_config.get('ae_mode', 'auto'),
                'exposure_time': csi_config.get('exposure_time', 10000),
                'analogue_gain': csi_config.get('analogue_gain', 1.0),
                'ae_metering_mode': csi_config.get('ae_metering_mode', 'centre'),
                'awb_mode': csi_config.get('awb_mode', 'auto'),
                'hdr_mode': csi_config.get('hdr_mode', False),
                'hdr_type': csi_config.get('hdr_type', 'multi'),
                'brightness': csi_config.get('brightness', 0.0),
                'contrast': csi_config.get('contrast', 1.0),
                'saturation': csi_config.get('saturation', 1.0),
                'sharpness': csi_config.get('sharpness', 1.0),
                'noise_reduction': csi_config.get('noise_reduction', 'fast'),
                'sensor_mode': csi_config.get('sensor_mode', 0),
                'fps_limit': csi_config.get('fps_limit', 30),
                'has_autofocus': True,
                'has_hdr': True,
            })
        
        # ВАЖНО: СОХРАНЯЕМ В self.csi_settings!
        self.csi_settings = settings
        
        # Логируем загруженные настройки
        print("\n📋 Загруженные настройки:")
        for key, value in self.csi_settings.items():
            if key not in ['name']:
                print(f"   {key}: {value}")
        print("="*60 + "\n")
        
        return self.csi_settings

    def log_current_camera_settings(self, frame=None):
        """Логирует текущие настройки камеры"""
        try:
            self.logger.info("=" * 70)
            self.logger.info("📸 ТЕКУЩИЕ НАСТРОЙКИ КАМЕРЫ ПРИ СНИМКЕ")
            self.logger.info("=" * 70)
            
            # Информация о типе камеры
            self.logger.info(f"🎥 Тип камеры: {self.camera_type}")
            self.logger.info(f"📷 Устройство: {self.config['camera'].get('device', 'unknown')}")
            
            if self.camera_type == 'csi' and self.current_picam2:
                # Для CSI камеры
                self.logger.info("\n🔧 НАСТРОЙКИ CSI КАМЕРЫ:")
                
                try:
                    # ===== ВАЖНО: Получаем РЕЖИМ ФОКУСА через get_controls =====
                    try:
                        controls_dict = self.current_picam2.get_controls()
                        
                        # Режим фокуса
                        if 'AfMode' in controls_dict:
                            af_mode_val = controls_dict['AfMode']
                            af_mode_str = {
                                0: "Manual",
                                1: "Auto",
                                2: "Continuous"
                            }.get(af_mode_val, f"Unknown ({af_mode_val})")
                            self.logger.info(f"   🔍 AfMode: {af_mode_str} (из get_controls)")
                        
                        # Позиция линзы
                        if 'LensPosition' in controls_dict:
                            self.logger.info(f"   ⚙️ LensPosition: {controls_dict['LensPosition']}")
                        
                        # Режим экспозиции
                        if 'AeEnable' in controls_dict:
                            self.logger.info(f"   ⚡ AeEnable: {controls_dict['AeEnable']}")
                        
                        if 'ExposureTime' in controls_dict:
                            self.logger.info(f"   ⏱️ ExposureTime: {controls_dict['ExposureTime']} мкс")
                        
                        if 'AnalogueGain' in controls_dict:
                            self.logger.info(f"   📈 AnalogueGain: {controls_dict['AnalogueGain']}")
                        
                        # Баланс белого
                        if 'AwbMode' in controls_dict:
                            awb_val = controls_dict['AwbMode']
                            awb_str = {
                                0: "Auto",
                                1: "Daylight",
                                2: "Tungsten",
                                3: "Fluorescent",
                                4: "Indoor",
                                5: "Cloudy"
                            }.get(awb_val, f"Unknown ({awb_val})")
                            self.logger.info(f"   🎨 AwbMode: {awb_str}")
                        
                        # HDR
                        if 'HdrMode' in controls_dict:
                            hdr_val = controls_dict['HdrMode']
                            hdr_str = {
                                0: "Off",
                                1: "Single",
                                2: "Multi",
                                3: "Night"
                            }.get(hdr_val, f"Unknown ({hdr_val})")
                            self.logger.info(f"   🌈 HdrMode: {hdr_str}")
                        
                    except Exception as e:
                        self.logger.warning(f"   ⚠️ Ошибка get_controls: {e}")
                    
                    # ===== МЕТАДАННЫЕ ПОСЛЕДНЕГО КАДРА =====
                    try:
                        metadata = self.current_picam2.capture_metadata()
                        if metadata:
                            self.logger.info("\n   📊 МЕТАДАННЫЕ ПОСЛЕДНЕГО КАДРА:")
                            for key in ['LensPosition', 'ExposureTime', 'AnalogueGain', 
                                    'DigitalGain', 'ColourGains', 'FocusFoM']:
                                if key in metadata:
                                    self.logger.info(f"      {key}: {metadata[key]}")
                    except:
                        pass
                    
                except Exception as e:
                    self.logger.warning(f"   ⚠️ Ошибка при чтении контролов: {e}")
            
            elif self.camera_type == 'v4l2' and self.current_v4l2_camera:
                # Для USB камеры
                self.logger.info("\n🔧 НАСТРОЙКИ USB КАМЕРЫ:")
                
                try:
                    # Разрешение
                    width = self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH)
                    height = self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    self.logger.info(f"   📐 Разрешение: {int(width)}x{int(height)}")
                    
                    # FPS
                    fps = self.current_v4l2_camera.get(cv2.CAP_PROP_FPS)
                    self.logger.info(f"   ⏱️ FPS: {fps:.1f}")
                    
                    # FOURCC кодек
                    fourcc_int = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FOURCC))
                    fourcc_str = chr(fourcc_int & 0xFF) + chr((fourcc_int >> 8) & 0xFF) + \
                                chr((fourcc_int >> 16) & 0xFF) + chr((fourcc_int >> 24) & 0xFF)
                    self.logger.info(f"   📼 FOURCC: {fourcc_str}")
                    
                    # Экспозиция
                    exposure = self.current_v4l2_camera.get(cv2.CAP_PROP_EXPOSURE)
                    self.logger.info(f"   ⚡ Exposure: {exposure}")
                    
                    # Баланс белого
                    wb = self.current_v4l2_camera.get(cv2.CAP_PROP_WHITE_BALANCE_BLUE_U)
                    self.logger.info(f"   🎨 White Balance: {wb}")
                    
                except Exception as e:
                    self.logger.warning(f"   ⚠️ Не удалось прочитать настройки USB: {e}")
            
            # Информация о кадре
            if frame is not None:
                h, w = frame.shape[:2]
                self.logger.info(f"\n📸 ПАРАМЕТРЫ КАДРА:")
                self.logger.info(f"   Размер: {w}x{h}")
                self.logger.info(f"   Каналы: {frame.shape[2] if len(frame.shape) > 2 else 1}")
                self.logger.info(f"   Тип данных: {frame.dtype}")
                
                # Статистика по яркости (если кадр цветной)
                if len(frame.shape) == 3:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    self.logger.info(f"   Средняя яркость: {gray.mean():.1f}")
                    self.logger.info(f"   Мин яркость: {gray.min()}")
                    self.logger.info(f"   Макс яркость: {gray.max()}")
            
            self.logger.info("=" * 70)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при логировании настроек: {e}")


    def _configure_csi_camera(self):
        """Настройка CSI камеры с учетом ее типа"""
        try:
            # 🔴 ДИАГНОСТИКА
            print(f"\n🔍 ========== _configure_csi_camera() ==========")
            print(f"🔍 self.csi_settings = {self.csi_settings}")
            
            # Проверяем, что настройки загружены
            if not self.csi_settings:
                print("❌ self.csi_settings пуст! Загружаем...")
                self._load_csi_settings()
            
            settings = self.csi_settings
            
            # Проверяем наличие обязательных ключей
            required_keys = ['name', 'width', 'height', 'ae_mode', 'has_autofocus']
            for key in required_keys:
                if key not in settings:
                    print(f"⚠️ Ключ '{key}' отсутствует, устанавливаем значение по умолчанию")
                    if key == 'name':
                        settings[key] = 'CSI Camera'
                    elif key == 'width':
                        settings[key] = 1920
                    elif key == 'height':
                        settings[key] = 1080
                    elif key == 'ae_mode':
                        settings[key] = 'auto'
                    elif key == 'has_autofocus':
                        settings[key] = True
            
            from libcamera import controls

            # Загружаем настройки если их нет
            if not self.csi_settings:
                print("📥 Загружаем настройки...")
                self._load_csi_settings()
            
            settings = self.csi_settings
            
            # Проверяем, что настройки загружены
            if not settings:
                print("❌ Не удалось загрузить настройки!")
                return
            
            print(f"\n📷 НАСТРОЙКА {settings['name']}")
            print("-"*60)
            print(f"   Разрешение: {settings['width']}x{settings['height']}")
            print(f"   Режим фокуса: {settings.get('af_mode', 'не задан')}")
            print(f"   Режим экспозиции: {settings.get('ae_mode', 'auto')}")
            
            # Создаем базовую конфигурацию
            config = self.current_picam2.create_video_configuration(
                main={"size": (settings['width'], settings['height'])}
            )
            self.current_picam2.configure(config)
            print("✅ Конфигурация применена")
            
            controls_to_set = {}
            
            # ===== НАСТРОЙКИ ЭКСПОЗИЦИИ =====
            if settings.get('ae_mode') == 'manual':
                controls_to_set["AeEnable"] = False
                controls_to_set["ExposureTime"] = int(settings.get('exposure_time', 10000))
                controls_to_set["AnalogueGain"] = float(settings.get('analogue_gain', 1.0))
                print(f"   ⚡ Экспозиция: Manual")
            else:
                controls_to_set["AeEnable"] = True
                print(f"   ⚡ Экспозиция: Auto")
            
            # ===== НАСТРОЙКИ АВТОФОКУСА =====
            if settings.get('has_autofocus', False):
                af_mode = settings.get('af_mode', 'continuous')
                print(f"   🔍 Режим фокуса: {af_mode}")
                
                if af_mode == 'manual':
                    controls_to_set["AfMode"] = controls.AfModeEnum.Manual
                    controls_to_set["LensPosition"] = float(settings.get('lens_position', 0.0))
                    
                elif af_mode == 'auto':
                    controls_to_set["AfMode"] = controls.AfModeEnum.Auto
                    
                else:  # continuous
                    controls_to_set["AfMode"] = controls.AfModeEnum.Continuous
                    controls_to_set["AfSpeed"] = controls.AfSpeedEnum.Fast
                
                # Окно фокуса
                if settings.get('af_window', False):
                    win_size = settings.get('af_window_size', 0.3)
                    win_w = int(settings['width'] * win_size)
                    win_h = int(settings['height'] * win_size)
                    win_x = (settings['width'] - win_w) // 2
                    win_y = (settings['height'] - win_h) // 2
                    controls_to_set["AfWindows"] = [(win_x, win_y, win_w, win_h)]
                    print(f"      Окно фокуса: {win_x},{win_y},{win_w},{win_h}")
            
            # Применяем настройки
            if controls_to_set:
                print(f"⚙️ Применяем контролы: {list(controls_to_set.keys())}")
                self.current_picam2.set_controls(controls_to_set)
                time.sleep(0.5)
            
            # ЗАПУСКАЕМ КАМЕРУ
            self.current_picam2.start()
            print("✅ Камера запущена")
            
            # ТРИГГЕР ТОЛЬКО ДЛЯ AUTO РЕЖИМА
            if settings.get('has_autofocus', False) and settings.get('af_mode') == 'auto':
                print("   🔍 Запускаю автофокус (триггер)...")
                self.current_picam2.set_controls({"AfTrigger": controls.AfTriggerEnum.Start})
                time.sleep(1.0)
                print("      ✅ Автофокус выполнен")
            
            # ПРОВЕРКА ФОКУСА
            try:
                metadata = self.current_picam2.capture_metadata()
                if metadata:
                    if 'LensPosition' in metadata:
                        print(f"   📍 Позиция линзы: {metadata['LensPosition']}")
                    if 'FocusFoM' in metadata:
                        print(f"   📊 Резкость: {metadata['FocusFoM']}")
                    if 'AfState' in metadata:
                        state_map = {0: "Idle", 1: "Scanning", 2: "Focused", 3: "Failed"}
                        print(f"   🔍 Состояние AF: {state_map.get(metadata['AfState'], metadata['AfState'])}")
            except:
                pass
            
            print(f"\n✅ {settings['name']} настроена и запущена")
            
        except Exception as e:
            print(f"❌ Ошибка настройки CSI камеры: {e}")
            import traceback
            traceback.print_exc()


    def cleanup_old_streams(self):
        """Очистка старых стримов"""
        with self.stream_lock:
            current_time = time.time()
            # Удаляем стримы старше 10 секунд
            old_streams = [cid for cid, ts in self.stream_sessions.items() 
                          if current_time - ts > 10.0]
            
            for client_id in old_streams:
                if self.active_streams > 0:
                    self.active_streams -= 1
                del self.stream_sessions[client_id]
                
            if old_streams:
                print(f"🧹 Очищено {len(old_streams)} старых стримов")
    
        # Перезапускаем таймер
        self.cleanup_timer = threading.Timer(30.0, self.cleanup_old_streams)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()

    def get_client_info(self):
        """Получение информации о клиенте"""
        if hasattr(request, 'remote_addr'):
            user_ip = request.remote_addr
        else:
            user_ip = 'unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')
        return user_ip, user_agent
    
    def capture_frames(self):
        """Захват кадров с камеры в буфер"""
        print(f"📹 Запущен поток захвата кадров. Тип камеры: {self.camera_type}")
        
        self.buffer_active = True
        frames_captured = 0
        error_count = 0
        max_errors = 30
        consecutive_errors = 0
        
        # ========== ДИАГНОСТИКА ПРИ ЗАПУСКЕ ==========
        if self.camera_type == 'csi' and self.current_picam2:
            try:
                print("\n🔍 ДИАГНОСТИКА CSI КАМЕРЫ:")
                
                # Проверяем, запущена ли камера
                if hasattr(self.current_picam2, 'started'):
                    print(f"   Камера запущена: {self.current_picam2.started}")
                
                # Получаем конфигурацию
                try:
                    config = self.current_picam2.camera_configuration()
                    if config and 'main' in config:
                        w, h = config['main']['size']
                        print(f"   Настроенное разрешение: {w}x{h}")
                except:
                    print("   ⚠️ Не удалось получить конфигурацию")
                
                # Пробуем получить тестовый кадр
                print("   Пробую получить тестовый кадр...")
                try:
                    test_array = self.current_picam2.capture_array()
                    if test_array is not None:
                        print(f"   ✅ Тестовый кадр получен! Формат: {test_array.shape}")
                        
                        if len(test_array.shape) == 3:
                            print(f"   📊 Каналы: {test_array.shape[2]}, тип: {test_array.dtype}")
                            
                            # Пробуем конвертировать
                            try:
                                test_frame = cv2.cvtColor(test_array, cv2.COLOR_RGB2BGR)
                                print(f"   ✅ Конвертация RGB->BGR успешна")
                            except:
                                print(f"   ⚠️ Ошибка конвертации, но это не критично")
                    else:
                        print("   ❌ Тестовый кадр не получен!")
                        consecutive_errors += 1
                except Exception as e:
                    print(f"   ❌ Ошибка получения тестового кадра: {e}")
                    consecutive_errors += 1
                    
            except Exception as e:
                print(f"   ❌ Ошибка диагностики CSI: {e}")
                import traceback
                traceback.print_exc()
        
        elif self.camera_type == 'v4l2' and self.current_v4l2_camera:
            try:
                # Какое разрешение мы хотим?
                target_width = self.config['camera'].get('width', 1024)
                target_height = self.config['camera'].get('height', 768)
                
                # Какое разрешение у камеры СЕЙЧАС?
                current_width = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                current_height = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                print(f"🎯 Желаемое разрешение: {target_width}x{target_height}")
                print(f"📸 Текущее разрешение камеры: {current_width}x{current_height}")
                
                # Пробуем принудительно установить
                print(f"🔄 Пробуем установить {target_width}x{target_height}...")
                
                self.current_v4l2_camera.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
                self.current_v4l2_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
                
                time.sleep(0.3)
                
                # Проверяем, что получилось
                new_width = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                new_height = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                print(f"✅ Новое разрешение: {new_width}x{new_height}")
                
                if new_width != target_width or new_height != target_height:
                    print(f"⚠️ Камера НЕ поддерживает {target_width}x{target_height}!")
                    print(f"📋 Поддерживаемые разрешения: 1920x1200, 1280x720, 640x480")
                    
            except Exception as e:
                print(f"❌ Ошибка диагностики USB: {e}")
        
        # ========== ОСНОВНОЙ ЦИКЛ ЗАХВАТА ==========
        while self.stream_active and self.buffer_active:
            try:
                frame = None
                
                # ----- CSI КАМЕРА -----
                if self.camera_type == 'csi' and self.current_picam2:
                    try:
                        # Проверяем, что камера запущена
                        if hasattr(self.current_picam2, 'started') and not self.current_picam2.started:
                            print("⚠️ Камера не запущена, пробую запустить...")
                            self.current_picam2.start()
                            time.sleep(0.5)
                            continue
                        
                        # Захватываем кадр
                        array = self.current_picam2.capture_array()
                        
                        if array is not None and array.size > 0:
                            # Конвертируем RGB -> BGR для OpenCV
                            if len(array.shape) == 3:
                                if array.shape[2] == 3:
                                    # Пробуем конвертировать
                                    try:
                                        frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                                    except:
                                        # Если не получается, используем как есть
                                        frame = array.copy()
                                        print(f"⚠️ Ошибка конвертации, использую исходный формат")
                                else:
                                    # Не 3 канала, используем как есть
                                    frame = array.copy()
                                    if frames_captured % 30 == 0:
                                        print(f"⚠️ Необычное число каналов: {array.shape[2]}")
                            else:
                                # Не 3-мерный массив
                                frame = array.copy()
                                if frames_captured % 30 == 0:
                                    print(f"⚠️ Необычная размерность: {array.shape}")
                            
                            # Сброс счетчика ошибок при успехе
                            consecutive_errors = 0
                            error_count = 0
                            
                        else:
                            # Кадр не получен
                            consecutive_errors += 1
                            error_count += 1
                            
                            if consecutive_errors >= max_errors:
                                print(f"❌ Слишком много ошибок подряд ({consecutive_errors}), перезапускаю камеру...")
                                try:
                                    self.current_picam2.stop()
                                    time.sleep(0.5)
                                    self.current_picam2.start()
                                    time.sleep(0.5)
                                    consecutive_errors = 0
                                    print("✅ Камера перезапущена")
                                except Exception as e:
                                    print(f"❌ Ошибка перезапуска: {e}")
                            
                            time.sleep(0.05)
                            continue
                            
                    except Exception as e:
                        consecutive_errors += 1
                        error_count += 1
                        
                        if consecutive_errors % 10 == 0:
                            print(f"❌ Ошибка захвата CSI: {e}")
                            if consecutive_errors >= max_errors:
                                print("⚠️ Слишком много ошибок, пытаюсь восстановиться...")
                                try:
                                    self.current_picam2.stop()
                                    time.sleep(0.5)
                                    self.current_picam2.start()
                                    consecutive_errors = 0
                                except:
                                    pass
                        
                        time.sleep(0.1)
                        continue
                
                # ----- USB КАМЕРА -----
                elif self.camera_type == 'v4l2' and self.current_v4l2_camera:
                    with self.camera_lock:
                        if self.current_v4l2_camera and self.current_v4l2_camera.isOpened():
                            try:
                                ret, frame = self.current_v4l2_camera.read()
                                
                                if ret and frame is not None:
                                    consecutive_errors = 0
                                    
                                    # Периодически проверяем разрешение
                                    if frames_captured % 100 == 0:
                                        h, w = frame.shape[:2]
                                        print(f"📐 Кадр USB #{frames_captured}: {w}x{h}")
                                else:
                                    consecutive_errors += 1
                                    if consecutive_errors % 10 == 0:
                                        print(f"⚠️ Ошибка чтения USB кадра #{consecutive_errors}")
                                    time.sleep(0.05)
                                    continue
                                    
                            except Exception as e:
                                consecutive_errors += 1
                                if consecutive_errors % 10 == 0:
                                    print(f"❌ Ошибка USB: {e}")
                                time.sleep(0.1)
                                continue
                
                # ===== ОБРАБОТКА УСПЕШНОГО КАДРА =====
                if frame is not None and frame.size > 0:
                    self.frame_count += 1
                    frames_captured += 1
                    
                    # Логируем каждые 30 кадров
                    if frames_captured % 30 == 0:
                        h, w = frame.shape[:2]
                        print(f"📊 Захвачено кадров: {frames_captured}, Тип: {self.camera_type}, Размер: {w}x{h}")
                    
                    # Сохраняем последний кадр
                    with self.frame_lock:
                        self.last_frame = frame.copy()
                    
                    # Добавляем в буфер (с ограничением размера)
                    try:
                        if self.frame_buffer.full():
                            try:
                                self.frame_buffer.get_nowait()
                            except queue.Empty:
                                pass
                        
                        self.frame_buffer.put_nowait(frame)
                    except Exception as e:
                        print(f"⚠️ Ошибка буфера: {e}")
                
                # Небольшая задержка для снижения нагрузки CPU
                time.sleep(0.01)
                
            except Exception as e:
                # Критическая ошибка в основном цикле
                if frames_captured % 10 == 0:
                    print(f"💥 Критическая ошибка в capture_frames: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Пытаемся восстановиться
                time.sleep(0.5)
                
                # Если ошибок слишком много, выходим
                error_count += 1
                if error_count > 100:
                    print("❌ Слишком много критических ошибок, останавливаю поток")
                    break
        
        print(f"📹 Поток захвата кадров остановлен. Всего кадров: {frames_captured}")
            
    def generate_from_buffer(self):
        """Генератор для получения кадров из буфера"""
        while self.stream_active:
            try:
                # Получаем кадр из буфера с таймаутом
                frame = self.frame_buffer.get(timeout=2.0)
                
                # Кодируем в JPEG
                jpeg_quality = self.config['camera'].get('jpeg_quality', 85)
                ret, jpeg = cv2.imencode('.jpg', frame, 
                                         [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           jpeg.tobytes() + b'\r\n')
                else:
                    time.sleep(0.01)
                    
            except queue.Empty:
                # Если буфер пуст, ждем немного
                time.sleep(0.1)
            except Exception as e:
                self.logger.log_error(f"Ошибка в generate_from_buffer: {e}")
                time.sleep(0.1)
    
    def get_fallback_image(self):
        """Возвращает статичное изображение при перегрузке"""
        # Создаем простое изображение
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (40, 40, 40)  # Серый фон
        
        # Добавляем текст
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, 'Too many streams', (150, 200), font, 1, (255, 255, 255), 2)
        cv2.putText(img, 'Please try again later', (120, 250), font, 0.7, (200, 200, 200), 2)
        
        ret, buffer = cv2.imencode('.jpg', img)
        frame_bytes = buffer.tobytes()
        
        return Response(
            b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n',
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def start_stream_internal(self):
        """Внутренний запуск стрима"""
        if not self.stream_active:
            print("=== DEBUG: start_stream_internal() called ===")
            
            # ВАЖНО: Полностью пересоздаем камеру для чистоты
            if self.camera_type == 'v4l2':
                # Закрываем старую камеру если есть
                if self.current_v4l2_camera:
                    self.current_v4l2_camera.release()
                    self.current_v4l2_camera = None
                    time.sleep(0.5)
                
                # Открываем заново
                device_path = self.config['camera'].get('device', '/dev/video8')
                print(f"📷 Открываю камеру {device_path}...")
                self.current_v4l2_camera = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
                
                if not self.current_v4l2_camera.isOpened():
                    print("❌ Не удалось открыть камеру")
                    return
                
                print("✅ Камера открыта")
            
            # ========== НАСТРОЙКА ПАРАМЕТРОВ ==========
            if self.camera_type == 'v4l2' and self.current_v4l2_camera:
                try:
                    
                    # Берем настройки из конфига
                    width = self.config['camera'].get('width', 1024)
                    height = self.config['camera'].get('height', 768)
                    fps = self.config['camera'].get('fps', 15)
                    
                    print(f"📷 НАСТРОЙКА USB камеры: {width}x{height} @ {fps}fps")
                    
                    # ВАЖНО: Порядок из теста - сначала кодек
                    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
                    print(f"🎬 Устанавливаю кодек MJPG...")
                    self.current_v4l2_camera.set(cv2.CAP_PROP_FOURCC, fourcc)
                    time.sleep(0.1)
                    
                    # Потом разрешение
                    print(f"📐 Устанавливаю разрешение {width}x{height}...")
                    self.current_v4l2_camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.current_v4l2_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    
                    # Устанавливаем FPS
                    self.current_v4l2_camera.set(cv2.CAP_PROP_FPS, fps)
                    
                    # Для глобального затвора
                    self.current_v4l2_camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                    
                    # Даем время на применение
                    time.sleep(0.3)
                    
                    # ПРОВЕРЯЕМ реальные настройки
                    actual_width = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = self.current_v4l2_camera.get(cv2.CAP_PROP_FPS)
                    actual_fourcc = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FOURCC))
                    
                    fourcc_str = chr(actual_fourcc & 0xFF) + chr((actual_fourcc >> 8) & 0xFF) + \
                                chr((actual_fourcc >> 16) & 0xFF) + chr((actual_fourcc >> 24) & 0xFF)
                    
                    print(f"✅ РЕАЛЬНЫЕ настройки: {actual_width}x{actual_height} @ {actual_fps:.1f}fps, кодек: {fourcc_str}")
                    
                    # ОБНОВЛЯЕМ КОНФИГ реальными значениями
                    self.config['camera']['width'] = actual_width
                    self.config['camera']['height'] = actual_height
                    self.config['camera']['fps'] = actual_fps
                    
                    # Проверяем захват кадра
                    ret, test_frame = self.current_v4l2_camera.read()
                    if ret and test_frame is not None:
                        h, w = test_frame.shape[:2]
                        print(f"📸 Тестовый кадр: {w}x{h}")
                    else:
                        print("⚠️ Не удалось получить тестовый кадр")
                    
                except Exception as e:
                    print(f"❌ Ошибка настройки USB камеры: {e}")
                    import traceback
                    traceback.print_exc()
            
            elif self.camera_type == 'csi' and self.current_picam2:
                try:
                    # ВАЖНО: Останавливаем камеру если она работает
                    try:
                        self.current_picam2.stop()
                        print("⏹️ CSI камера остановлена")
                        time.sleep(0.5)
                    except:
                        pass
                    
                    # ЗАГРУЖАЕМ НАСТРОЙКИ
                    self._load_csi_settings()
                    
                    # КОНФИГУРИРУЕМ КАМЕРУ
                    self._configure_csi_camera()
                    
                except Exception as e:
                    print(f"❌ Ошибка настройки CSI камеры: {e}")
                    import traceback
                    traceback.print_exc()
            # ========== КОНЕЦ НАСТРОЙКИ ==========
            
            # ПРИНУДИТЕЛЬНЫЙ СБРОС БУФЕРА ПЕРЕД ЗАПУСКОМ
            if not self.frame_buffer.empty():
                print("⚠️ Буфер не пуст перед запуском, очищаем...")
                cleared = 0
                while not self.frame_buffer.empty():
                    try:
                        self.frame_buffer.get_nowait()
                        cleared += 1
                    except queue.Empty:
                        break
                print(f"✅ Очищено {cleared} элементов из буфера")
            
            self.stream_active = True
            self.buffer_active = True
            self.frame_count = 0
            
            # Убедимся, что старый поток завершен
            if self.buffer_thread and self.buffer_thread.is_alive():
                print("⚠️ Старый поток все еще активен, останавливаем...")
                self.buffer_active = False
                self.buffer_thread.join(timeout=1.0)
                self.buffer_thread = None
            
            # Запускаем новый поток захвата кадров
            self.buffer_thread = threading.Thread(target=self.capture_frames, daemon=True)
            self.buffer_thread.start()
            
            # Ждем немного чтобы поток успел стартовать
            time.sleep(0.1)
            
            print("✅ Стрим запущен")
            self.logger.log_info("Стрим видеопотока запущен")
            
            # Выводим состояние через 0.5 секунды
            def delayed_check():
                time.sleep(0.5)
                print(f"📊 Проверка через 0.5с: Поток жив: {self.buffer_thread.is_alive() if self.buffer_thread else False}, "
                    f"Буфер: {self.frame_buffer.qsize()}")
                
                # Дополнительная проверка разрешения после запуска
                if self.camera_type == 'v4l2' and self.current_v4l2_camera:
                    try:
                        w = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        print(f"📸 Реальное разрешение в потоке: {w}x{h}")
                    except:
                        pass
            
            threading.Thread(target=delayed_check, daemon=True).start()
        
    def stop_stream_internal(self):
        """Внутренняя остановка стрима"""
        if self.stream_active:
            print("=== DEBUG: stop_stream_internal() called ===")
            print(f"📊 Текущий размер буфера: {self.frame_buffer.qsize()}")
            
            # Сначала останавливаем захват
            self.stream_active = False
            self.buffer_active = False
            
            # Полностью очищаем буфер ПЕРЕД остановкой потока
            print("🧹 Очистка буфера...")
            buffer_items_cleared = 0
            while not self.frame_buffer.empty():
                try:
                    self.frame_buffer.get_nowait()
                    buffer_items_cleared += 1
                except queue.Empty:
                    break
            print(f"✅ Очищено элементов буфера: {buffer_items_cleared}")
            
            # Затем останавливаем поток
            if self.buffer_thread and self.buffer_thread.is_alive():
                print("⏳ Ожидание завершения потока захвата...")
                self.buffer_thread.join(timeout=2.0)
                if self.buffer_thread.is_alive():
                    print("⚠️ Поток захчета не завершился вовремя")
                self.buffer_thread = None
            
            print("📹 Стрим остановлен")
            self.logger.log_info("Стрим видеопотока остановлен")
        
    def restart_stream_async(self):
        """Асинхронный перезапуск стрима"""
        time.sleep(0.5)
        self.start_stream_internal()

    def capture_frame_to_file(self):
        """Захват одного кадра и сохранение в файл"""
        try:
            frame = None
            
            if self.camera_type == 'csi':
                # Захват с CSI камеры
                if self.current_picam2:
                    try:
                        array = self.current_picam2.capture_array()
                        if array is not None and len(array.shape) == 3 and array.shape[2] == 3:
                            frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        self.logger.log_error(f"Ошибка захвата CSI кадра: {e}")
                        return None
            else:
                # Захват с USB камеры через V4L2
                with self.camera_lock:
                    if self.current_v4l2_camera and self.current_v4l2_camera.isOpened():
                        ret, frame = self.current_v4l2_camera.read()
                        if not ret or frame is None:
                            self.logger.log_error("Не удалось прочитать кадр с USB камеры")
                            return None
            
            return frame
            
        except Exception as e:
            self.logger.log_error(f"Ошибка в capture_frame_to_file: {e}")
            return None        
        
    @staticmethod    
    def format_file_size(bytes_size):
        """Форматирование размера файла в читаемый вид"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"        
    
    def setup_routes(self):
        """Настройка маршрутов Flask"""
        
        @self.app.before_request
        def log_request():
            """Логирование всех запросов"""
            if request.endpoint and request.endpoint not in ['static', 'video_feed']:
                user_ip, user_agent = self.get_client_info()
                self.logger.log_info(f"🌐 Запрос: {request.method} {request.path}")
        
        # ОБЯЗАТЕЛЬНО: Маршрут главной страницы
        @self.app.route('/')
        def index():
            """Главная страница"""
            try:
                return render_template('index.html')
            except Exception as e:
                return f'''
                <html>
                <head><title>Webcam Stream</title></head>
                <body>
                    <h1>🎥 Webcam Stream</h1>
                    <p>Сервер работает!</p>
                    <p>Шаблон не найден, создайте index.html в папке templates</p>
                    <p><a href="/status">Статус</a> | <a href="/logs">Логи</a></p>
                </body>
                </html>
                '''
        
        @self.app.route('/video_feed')
        def video_feed():
            """Маршрут для видео потока с ограничением"""
            # Получаем IP клиента
            client_ip = request.remote_addr if hasattr(request, 'remote_addr') else 'unknown'
            client_id = f"{client_ip}_{request.args.get('t', str(time.time()))}"
            
            with self.stream_lock:
                # Проверяем лимит для конкретного клиента
                client_streams = self.active_clients.get(client_ip, 0)
                if client_streams >= self.MAX_STREAMS_PER_CLIENT:
                    print(f"⚠️  Клиент {client_ip} уже имеет активный стрим")
                    return self.get_fallback_image()
                
                # Проверяем общий лимит
                if self.active_streams >= self.MAX_CONCURRENT_STREAMS:
                    print(f"⚠️  Превышено общее количество стримов: {self.active_streams}/{self.MAX_CONCURRENT_STREAMS}")
                    return self.get_fallback_image()
                
                # Увеличиваем счетчики
                self.active_streams += 1
                self.active_clients[client_ip] = client_streams + 1
                
                print(f"📹 Клиент {client_ip} запросил video_feed (клиентских: {client_streams+1}, всего: {self.active_streams})")
            
            def generate_with_cleanup():
                try:
                    for chunk in self.generate_from_buffer():
                        yield chunk
                except GeneratorExit:
                    print(f"📹 Клиент {client_ip} отключился")
                except Exception as e:
                    print(f"📹 Ошибка: {e}")
                finally:
                    with self.stream_lock:
                        # Уменьшаем счетчики
                        if self.active_streams > 0:
                            self.active_streams -= 1
                        
                        client_streams = self.active_clients.get(client_ip, 0)
                        if client_streams > 0:
                            self.active_clients[client_ip] = client_streams - 1
                            if self.active_clients[client_ip] <= 0:
                                del self.active_clients[client_ip]
                        
                        print(f"📹 Стрим завершен для {client_ip} (осталось: клиентских: {self.active_clients.get(client_ip,0)}, всего: {self.active_streams})")
            
            return Response(generate_with_cleanup(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
            
        @self.app.route('/api/stream/start', methods=['POST'])
        def start_stream():
            """Запуск видеопотока"""
            user_ip, user_agent = self.get_client_info()
            
            if not self.stream_active:
                # Проверяем камеру в зависимости от типа
                camera_ready = False
                
                if self.camera_type == 'csi':
                    # CSI камера
                    camera_ready = self.current_picam2 is not None
                else:
                    # USB камера через V4L2
                    with self.camera_lock:
                        if self.current_v4l2_camera:
                            try:
                                camera_ready = self.current_v4l2_camera.isOpened()
                            except:
                                camera_ready = False
                
                if not camera_ready:
                    self.logger.log_web_action('start_stream', 'error', 'Camera not ready', user_ip, user_agent)
                    return jsonify({'status': 'error', 'message': 'Камера не готова'})
                
                self.start_stream_internal()
                
                self.logger.log_web_action('start_stream', 'success', 
                                        f"Stream started (type: {self.camera_type})",
                                        user_ip, user_agent)
                self.logger.log_button_click('start_stream', 'index', user_ip)
                return jsonify({'status': 'started', 'message': 'Видеопоток запущен', 'camera_type': self.camera_type})
            else:
                self.logger.log_web_action('start_stream', 'warning', 'Stream already running',
                                        user_ip, user_agent)
                return jsonify({'status': 'already_running', 'message': 'Видеопоток уже запущен'})
        
        @self.app.route('/api/stream/stop', methods=['POST'])
        def stop_stream():
            """Остановка видеопотока"""
            user_ip, user_agent = self.get_client_info()
            
            if self.stream_active:
                self.stop_stream_internal()
                
                self.logger.log_web_action('stop_stream', 'success', 
                                        f"Stream stopped on {self.config['camera']['device']}",
                                        user_ip, user_agent)
                self.logger.log_button_click('stop_stream', 'index', user_ip)
                return jsonify({'status': 'stopped', 'message': 'Видеопоток остановлен'})
            else:
                self.logger.log_web_action('stop_stream', 'warning', 'Stream already stopped',
                                        user_ip, user_agent)
                return jsonify({'status': 'already_stopped', 'message': 'Видеопоток уже остановлен'})
        
        @self.app.route('/api/stream/status')
        def stream_status():
            """Получение статуса видеопотока"""
            # Проверяем состояние камеры в зависимости от типа
            camera_ready = False
            camera_device = ""
            
            if self.camera_type == 'csi':
                # CSI камера через Picamera2
                if self.current_picam2:
                    try:
                        camera_ready = True  # Picamera2 не имеет метода isOpened()
                        camera_device = f"csi_{self.csi_manager.current_camera}"
                    except:
                        camera_ready = False
            else:
                # USB камера через V4L2
                with self.camera_lock:
                    if self.current_v4l2_camera:
                        try:
                            camera_ready = self.current_v4l2_camera.isOpened()
                            # Получаем device из конфига, но конвертируем в строку если нужно
                            device_config = self.config['camera']['device']
                            if isinstance(device_config, int):
                                camera_device = f"/dev/video{device_config}"
                            else:
                                camera_device = str(device_config)
                        except:
                            camera_ready = False
            
            return jsonify({
                'stream_active': self.stream_active,
                'frame_count': self.frame_count,
                'camera_ready': camera_ready,
                'camera_device': camera_device,
                'camera_type': self.camera_type,
                'config': {
                    'device': str(self.config['camera']['device']),  # Преобразуем в строку
                    'backend': self.config['camera']['backend'],
                    'resolution': f"{self.config['camera'].get('width', 'auto')}x{self.config['camera'].get('height', 'auto')}",
                    'fps': self.config['camera'].get('fps', 'auto'),
                    'jpeg_quality': self.config['camera']['jpeg_quality']
                }
            })
        
        @self.app.route('/api/cameras')
        def get_cameras():
            """Получение списка доступных камер (USB + CSI)"""
            try:
                available_cameras = []
                
                # 1. USB камеры через V4L2 (исключая CSI)
                usb_cameras = self.camera_checker.get_cameras_for_api()
                
                # ОТЛАДКА: выведем все USB камеры, которые вернул CameraChecker
                print(f"🔍 CameraChecker вернул {len(usb_cameras)} камер:")
                for i, cam in enumerate(usb_cameras):
                    print(f"  {i}: {cam.get('device_path')} - {cam.get('name')} - is_camera={cam.get('is_camera')}")
                
                # Используем метод из CameraChecker для проверки
                for cam in usb_cameras:
                    name = cam.get('name', '')
                    device_path = cam.get('device_path', '')
                    
                    # ПРОВЕРЯЕМ: пропускаем CSI камеры, используя метод из CameraChecker
                    if self.camera_checker._is_csi_camera_by_name(name):
                        print(f"🔄 Пропускаем CSI камеру в USB списке: {name} ({device_path})")
                        continue
                    
                    # ИСПРАВЛЕНИЕ: Добавляем камеру, если она имеет is_camera=True ИЛИ
                    # если это явно USB камера (по имени или пути)
                    is_usb_camera = 'usb' in device_path.lower() or 'usb' in name.lower()
                    has_formats = cam.get('formats') and len(cam.get('formats', [])) > 0
                    
                    if cam.get('is_camera', False) or is_usb_camera or has_formats:
                        cam['type'] = 'USB'  # Явно указываем тип
                        cam['device_path'] = device_path
                        cam['is_current'] = False
                        
                        # Проверяем, является ли эта камера текущей
                        if self.camera_type == 'v4l2' and self.current_v4l2_camera:
                            current_path = self.config['camera'].get('device', '')
                            if isinstance(current_path, int):
                                current_path = f"/dev/video{current_path}"
                            cam['is_current'] = cam['device_path'] == current_path
                        
                        print(f"✅ Добавляем USB камеру: {device_path} - {name}")
                        available_cameras.append(cam)
                    else:
                        print(f"❌ Пропускаем камеру (не is_camera): {device_path} - {name}")
                
                # 2. 🔴 ИСПРАВЛЕНО: CSI камеры с проверкой на None
                if hasattr(self, 'csi_manager') and self.csi_manager is not None:
                    try:
                        if hasattr(self.csi_manager, 'cameras') and self.csi_manager.cameras:
                            for cam in self.csi_manager.cameras:
                                csi_info = {
                                    'device_path': f"csi_{cam['index']}",
                                    'name': cam['name'],
                                    'type': 'CSI',  # Явно указываем тип
                                    'formats': ['RGB888', 'BGR888'],
                                    'resolutions': ['4608x2592', '1920x1080', '1280x720'],
                                    'is_camera': True,
                                    'is_current': False
                                }
                                # Проверяем, является ли эта CSI камера текущей
                                if self.camera_type == 'csi' and self.csi_manager.current_camera == cam['index']:
                                    csi_info['is_current'] = True
                                available_cameras.append(csi_info)
                        else:
                            print("ℹ️ CSI камеры не найдены или список пуст")
                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке CSI камер: {e}")
                else:
                    print("ℹ️ CSI менеджер не инициализирован")
                
                print(f"📊 Итого добавлено камер в API: {len(available_cameras)}")
                
                return jsonify({
                    'cameras': available_cameras,
                    'total': len(available_cameras),
                    'current_camera_type': self.camera_type,
                    'current_device': self.config['camera'].get('device', '')
                })
                
            except Exception as e:
                print(f"❌ Ошибка получения списка камер: {e}")
                import traceback
                traceback.print_exc()  # Это покажет точную строку ошибки
                self.logger.log_error(f"Ошибка получения списка камер: {e}")
                return jsonify({
                    'cameras': [],
                    'total': 0, 
                    'error': str(e),
                    'current_camera_type': self.camera_type
                })
                
        @self.app.route('/api/cameras/select', methods=['POST'])
        def select_camera():
            """Выбор камеры для стрима (USB или CSI)"""
            user_ip, user_agent = self.get_client_info()  # Используем self
            
            try:
                device_path = request.json.get('device_path')
                if not device_path:
                    return jsonify({'status': 'error', 'message': 'Не указан путь к устройству'})
                
                # Получаем текущее состояние стрима
                was_streaming = self.stream_active  # Используем self
                
                # Если стрим активен, временно приостанавливаем
                if self.stream_active:  # Используем self
                    self.stop_stream_internal()  # Используем self
                
                # Определяем тип камеры
                if device_path.startswith('csi_'):
                    # Это CSI камера
                    try:
                        camera_idx = int(device_path.split('_')[1])
                        
                        # Закрываем текущую камеру
                        if self.camera_type == 'csi':  # Используем self
                            self.csi_manager.close_current()  # Используем self
                        elif self.camera_type == 'v4l2' and self.current_v4l2_camera:  # Используем self
                            self.current_v4l2_camera.release()  # Используем self
                        
                        # Открываем CSI камеру
                        picam2 = self.csi_manager.open_csi_camera(camera_idx)  # Используем self
                        if picam2:
                            self.camera_type = 'csi'  # Используем self
                            self.current_picam2 = picam2  # Используем self
                            self.current_v4l2_camera = None  # Используем self
                            self.config['camera']['device'] = device_path  # Используем self
                            
                            print(f"📹 Переключились на CSI камеру #{camera_idx}")
                            
                            # Возобновляем стрим если он был активен
                            if was_streaming:
                                self.start_stream_internal()  # Используем self
                            
                            return jsonify({
                                'status': 'success',
                                'message': f'Переключились на CSI камеру #{camera_idx}',
                                'device_path': device_path,
                                'type': 'CSI'
                            })
                        else:
                            return jsonify({'status': 'error', 'message': 'Не удалось открыть CSI камеру'})
                            
                    except Exception as e:
                        return jsonify({'status': 'error', 'message': f'Ошибка CSI камеры: {str(e)}'})
                
                else:
                    # Это USB камера через V4L2
                    # Закрываем текущую камеру
                    if self.camera_type == 'csi':  # Используем self
                        self.csi_manager.close_current()  # Используем self
                        self.current_picam2 = None  # Используем self
                    elif self.camera_type == 'v4l2' and self.current_v4l2_camera:  # Используем self
                        self.current_v4l2_camera.release()  # Используем self
                    
                    # Открываем USB камеру
                    with self.camera_lock:  # Используем self
                        try:
                            new_camera = cv2.VideoCapture(device_path)
                            if new_camera.isOpened():
                                # Настраиваем параметры
                                if 'width' in self.config['camera'] and 'height' in self.config['camera']:  # Используем self
                                    new_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['camera']['width'])
                                    new_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['camera']['height'])
                                
                                self.current_v4l2_camera = new_camera  # Используем self
                                self.camera_type = 'v4l2'  # Используем self
                                self.current_picam2 = None  # Используем self
                                self.config['camera']['device'] = device_path  # Используем self
                                self.frame_count = 0  # Используем self
                                
                                print(f"📹 Переключились на USB камеру {device_path}")
                                
                                # Возобновляем стрим если он был активен
                                if was_streaming:
                                    self.start_stream_internal()  # Используем self
                                
                                return jsonify({
                                    'status': 'success',
                                    'message': f'Переключились на USB камеру {device_path}',
                                    'device_path': device_path,
                                    'type': 'USB'
                                })
                            else:
                                return jsonify({'status': 'error', 'message': 'Не удалось открыть USB камеру'})
                                
                        except Exception as e:
                            return jsonify({'status': 'error', 'message': f'Ошибка USB камеры: {str(e)}'})
                            
            except Exception as e:
                return jsonify({'status': 'error', 'message': f'Неожиданная ошибка: {str(e)}'})


        @self.app.route('/api/camera/focus', methods=['POST'])
        def trigger_focus():
            """Принудительный запуск автофокуса"""
            try:
                if self.camera_type != 'csi' or not self.current_picam2:
                    return jsonify({'status': 'error', 'message': 'CSI камера не активна'}), 400
                
                from libcamera import controls
                
                # Получаем текущую позицию ДО
                metadata = self.current_picam2.capture_metadata()
                before_pos = metadata.get('LensPosition', 'unknown')
                
                print(f"🔍 До автофокуса: позиция {before_pos}")
                
                # ===== ВАЖНО: ПЕРЕКЛЮЧАЕМСЯ В AUTO РЕЖИМ =====
                print("   Переключаю в режим Auto...")
                self.current_picam2.set_controls({
                    "AfMode": controls.AfModeEnum.Auto
                })
                time.sleep(0.2)
                
                # ===== ЗАПУСКАЕМ АВТОФОКУС =====
                print("   Запускаю триггер автофокуса...")
                self.current_picam2.set_controls({
                    "AfTrigger": controls.AfTriggerEnum.Start
                })
                
                # Ждем завершения фокусировки
                time.sleep(1.5)
                
                # Получаем позицию ПОСЛЕ
                metadata = self.current_picam2.capture_metadata()
                after_pos = metadata.get('LensPosition', 'unknown')
                fom = metadata.get('FocusFoM', 'unknown')
                
                print(f"✅ После автофокуса: позиция {after_pos}, резкость {fom}")
                
                # ОПЦИОНАЛЬНО: возвращаемся в Continuous если нужно
                # self.current_picam2.set_controls({
                #     "AfMode": controls.AfModeEnum.Continuous
                # })
                
                return jsonify({
                    'status': 'success',
                    'message': 'Автофокус запущен',
                    'lens_position_before': before_pos,
                    'lens_position_after': after_pos,
                    'focus_fom': fom
                })
                
            except Exception as e:
                print(f"❌ Ошибка автофокуса: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500


        @self.app.route('/api/camera/focus/manual', methods=['POST'])
        def set_manual_focus():
            """Установка ручного фокуса"""
            try:
                data = request.get_json()
                lens_position = data.get('position', 0.0)
                
                if self.camera_type != 'csi' or not self.current_picam2:
                    return jsonify({'status': 'error', 'message': 'CSI камера не активна'}), 400
                
                from libcamera import controls
                
                # Устанавливаем ручной режим и позицию
                self.current_picam2.set_controls({
                    "AfMode": controls.AfModeEnum.Manual,
                    "LensPosition": float(lens_position)
                })
                
                # Проверяем результат
                time.sleep(0.3)
                metadata = self.current_picam2.capture_metadata()
                actual_pos = metadata.get('LensPosition', 'unknown')
                
                return jsonify({
                    'status': 'success',
                    'message': f'Фокус установлен на {lens_position}',
                    'actual_position': actual_pos
                })
                
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500                

        @self.app.route('/api/camera/debug_controls', methods=['GET'])
        def debug_controls():
            """Отладка всех доступных контролов"""
            try:
                if self.camera_type != 'csi' or not self.current_picam2:
                    return jsonify({'status': 'error', 'message': 'CSI камера не активна'}), 400
                
                result = {
                    'get_controls': {},
                    'metadata': {},
                    'controls_attrs': []
                }
                
                # 1. Получаем все через get_controls()
                try:
                    controls_dict = self.current_picam2.get_controls()
                    for key, value in controls_dict.items():
                        result['get_controls'][key] = str(value)
                except Exception as e:
                    result['get_controls_error'] = str(e)
                
                # 2. Метаданные
                try:
                    metadata = self.current_picam2.capture_metadata()
                    for key, value in metadata.items():
                        result['metadata'][key] = str(value)
                except Exception as e:
                    result['metadata_error'] = str(e)
                
                # 3. Атрибуты controls
                try:
                    result['controls_attrs'] = dir(self.current_picam2.controls)
                except Exception as e:
                    pass
                
                return jsonify({
                    'status': 'success',
                    'debug_info': result,
                    'config_fps': self.config['camera'].get('fps', 30),
                    'config_af_mode': self.config.get('csi_cameras', {}).get('csi_0', {}).get('af_mode', 'unknown')
                })
                
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500


        @self.app.route('/status')
        def status_page():
            """Страница статуса сервера"""
            user_ip, user_agent = self.get_client_info()
            self.logger.log_web_action('page_load', 'success', 'Status page loaded', user_ip, user_agent)
            return render_template('status.html')
        
        @self.app.route('/logs')
        def logs_page():
            """Страница с логами (HTML)"""
            user_ip, user_agent = self.get_client_info()
            self.logger.log_web_action('page_load', 'success', 'Logs page loaded', user_ip, user_agent)
            return render_template('logs.html')

        @self.app.route('/api/logs')
        def get_logs_api():
            """API для получения логов в формате JSON"""
            try:
                # Получаем логи через логгер
                raw_logs = self.logger.get_logs(limit=50)
                
                # Форматируем для фронтенда
                formatted_logs = []
                for log in raw_logs:
                    formatted_logs.append({
                        #'type': log.get('type', 'info'),
                        'message': log.get('raw', ''),
                        #'timestamp': log.get('timestamp', '')
                    })
                
                return jsonify({
                    'success': True,
                    'logs': formatted_logs,
                    'count': len(formatted_logs),
                    'log_file': os.path.basename(self.logger.log_file) if hasattr(self.logger, 'log_file') else 'unknown'
                })
                
            except Exception as e:
                # Логируем ошибку
                self.logger.error(f"API /api/logs error: {str(e)}")
                
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'logs': [
                        {
                            'type': 'error',
                            'message': f'Ошибка получения логов: {str(e)}',
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                    ]
                }), 500
        
        @self.app.route('/api/camera/test', methods=['GET'])
        def test_camera():
            """Тест камеры - попытка чтения кадра"""
            if self.camera_type == 'csi':  # Используем self
                # CSI камера
                if self.current_picam2 is None:
                    return jsonify({'status': 'error', 'message': 'CSI камера не инициализирована'})
                
                try:
                    frame = self.csi_manager.capture_frame()  # Используем self
                    if frame is not None:
                        return jsonify({
                            'status': 'success',
                            'message': 'CSI камера работает',
                            'resolution': f'{frame.shape[1]}x{frame.shape[0]}',
                            'fps': 30,
                            'frame_size': f'{frame.shape[1]}x{frame.shape[0]}',
                            'type': 'CSI'
                        })
                    else:
                        return jsonify({'status': 'error', 'message': 'Не удалось прочитать кадр с CSI камеры'})
                        
                except Exception as e:
                    return jsonify({'status': 'error', 'message': f'Ошибка CSI камеры: {str(e)}'})
            
            else:
                # USB камера через V4L2
                with self.camera_lock:  # Используем self
                    if self.current_v4l2_camera is None:
                        return jsonify({'status': 'error', 'message': 'Камера не инициализирована'})
                    
                    if not self.current_v4l2_camera.isOpened():
                        return jsonify({'status': 'error', 'message': 'Камера не открыта'})
                    
                    success, frame = self.current_v4l2_camera.read()
                    if success and frame is not None:
                        # Пробуем получить параметры камеры
                        width = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = int(self.current_v4l2_camera.get(cv2.CAP_PROP_FPS))
                        
                        return jsonify({
                            'status': 'success',
                            'message': 'Камера работает',
                            'resolution': f'{width}x{height}',
                            'fps': fps,
                            'frame_size': f'{frame.shape[1]}x{frame.shape[0]}',
                            'type': 'USB'
                        })
                    else:
                        return jsonify({'status': 'error', 'message': 'Не удалось прочитать кадр'})

        @self.app.route('/api/stream/diagnostics')
        def stream_diagnostics():
            """Диагностика состояния стрима"""
            return jsonify({
                'status': 'success',
                'diagnostics': self.get_stream_state_info()
            })

        @self.app.route('/api/stream/test_generator')
        def test_generator():
            """Тест генератора кадров"""
            def generate_test():
                try:
                    frame_count = 0
                    while self.stream_active:
                        try:
                            frame = self.frame_buffer.get(timeout=2.0)
                            frame_count += 1
                            yield f"data: Кадр {frame_count} получен, размер буфера: {self.frame_buffer.qsize()}\n\n"
                        except queue.Empty:
                            yield f"data: Буфер пуст (таймаут), активных потоков: {self.active_streams}\n\n"
                            time.sleep(0.1)
                        except Exception as e:
                            yield f"data: Ошибка: {str(e)}\n\n"
                            time.sleep(0.1)
                except Exception as e:
                    yield f"data: Генератор завершен: {str(e)}\n\n"
            
            return Response(generate_test(), mimetype='text/event-stream')


        @self.app.route('/api/camera/capture', methods=['POST'])
        def capture_picture():
            """Захват и сохранение снимка с камеры"""
            user_ip, user_agent = self.get_client_info()
            
            try:
                # Проверяем, запущен ли стрим
                if not self.stream_active:
                    self.logger.log_web_action('capture_picture', 'error', 
                                            'Stream not active', user_ip, user_agent)
                    return jsonify({
                        'status': 'error',
                        'message': 'Стрим не запущен. Запустите стрим сначала.'
                    }), 400
                
                self.logger.log_web_action('capture_picture', 'info', 
                                        'Starting picture capture', user_ip, user_agent)
                
                # Создаем папку для сохранения снимков
                
                photos_dir = os.path.join(current_dir, 'static', 'photos')
                os.makedirs(photos_dir, exist_ok=True)
                
                # Получаем кадр
                frame = self.capture_frame_to_file()
                if frame is None:
                    self.logger.log_web_action('capture_picture', 'error', 
                                            'Failed to capture frame', user_ip, user_agent)
                    return jsonify({
                        'status': 'error',
                        'message': 'Не удалось получить кадр с камеры'
                    }), 500
                
                self.log_current_camera_settings(frame)

                # Генерируем имя файла
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"photo_{timestamp}.jpg"
                filepath = os.path.join(photos_dir, filename)
                
                # Сохраняем изображение
                jpeg_quality = self.config['camera'].get('jpeg_quality', 85)
                success = cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                
                if not success:
                    self.logger.log_web_action('capture_picture', 'error', 
                                            'Failed to save image', user_ip, user_agent)
                    return jsonify({
                        'status': 'error',
                        'message': 'Не удалось сохранить изображение'
                    }), 500
                
                # Получаем размер файла
                file_size = os.path.getsize(filepath)
                size_str = f"{file_size / 1024:.1f} KB"
                
                # URL для доступа к файлу
                preview_url = f"/static/photos/{filename}"
                
                # Логируем успех
                self.logger.log_web_action('capture_picture', 'success', 
                                        f'Picture saved: {filename} ({size_str})', 
                                        user_ip, user_agent)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Снимок успешно сохранен',
                    'filename': filename,
                    'filepath': filepath,
                    'preview_url': preview_url,
                    'size': size_str,
                    'timestamp': timestamp,
                    'resolution': f'{frame.shape[1]}x{frame.shape[0]}'
                })
                
            except Exception as e:
                error_msg = f"Ошибка при создании снимка: {str(e)}"
                self.logger.log_error(error_msg)
                self.logger.log_web_action('capture_picture', 'error', 
                                        error_msg, user_ip, user_agent)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 500


        @self.app.route('/api/photos')
        def get_photos_list():
            """Получение списка всех сохраненных фотографий"""
            try:
                # Проверяем существование папки
                if not os.path.exists(self.photos_dir):
                    os.makedirs(self.photos_dir, exist_ok=True)
                    return jsonify({
                        'status': 'success',
                        'photos': [],
                        'count': 0,
                        'message': 'Папка создана, фото пока нет'
                    })
                
                # Получаем список файлов
                photos = []
                for filename in sorted(os.listdir(self.photos_dir), reverse=True):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        filepath = os.path.join(self.photos_dir, filename)
                        
                        if os.path.isfile(filepath):
                            # Получаем информацию о файле
                            stat = os.stat(filepath)
                            
                            # Определяем размер изображения
                            try:
                                img = cv2.imread(filepath)
                                if img is not None:
                                    width, height = img.shape[1], img.shape[0]
                                else:
                                    width, height = 0, 0
                            except:
                                width, height = 0, 0
                            
                            photos.append({
                                'filename': filename,
                                'url': f'/static/photos/{filename}',
                                'filepath': filepath,
                                'size_bytes': stat.st_size,
                                'size_formatted': self.format_file_size(stat.st_size),
                                'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'resolution': f'{width}x{height}',
                                'type': 'image/jpeg'
                            })
                
                # Ограничиваем количество возвращаемых фото (последние 50)
                limited_photos = photos[:50]
                
                return jsonify({
                    'status': 'success',
                    'photos': limited_photos,
                    'count': len(photos),
                    'limited_count': len(limited_photos),
                    'total_size': self.format_file_size(sum(p['size_bytes'] for p in photos)),
                    'photos_dir': self.photos_dir,
                    'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
            except Exception as e:
                error_msg = f"Ошибка получения списка фото: {str(e)}"
                self.logger.log_error(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg,
                    'photos': []
                }), 500

        @self.app.route('/api/photos/delete/<filename>', methods=['DELETE'])
        def delete_photo(filename):
            """Удаление фотографии"""
            try:
                # Безопасность: проверяем, что это допустимое имя файла
                import re
                if not re.match(r'^photo_\d{8}_\d{6}_\d{6}\.jpg$', filename):
                    return jsonify({
                        'status': 'error',
                        'message': 'Некорректное имя файла'
                    }), 400
                
                filepath = os.path.join(self.photos_dir, filename)
                
                # Проверяем, что файл существует и внутри разрешенной директории
                real_photos_path = os.path.realpath(self.photos_dir)
                real_file_path = os.path.realpath(filepath)
                
                if not os.path.exists(filepath):
                    return jsonify({
                        'status': 'error',
                        'message': 'Файл не найден'
                    }), 404
                    
                if not real_file_path.startswith(real_photos_path):
                    return jsonify({
                        'status': 'error', 
                        'message': 'Доступ запрещен'
                    }), 403
                
                # Удаляем файл
                os.remove(filepath)
                
                self.logger.log_web_action('delete_photo', 'success', 
                                        f'Deleted: {filename}', 
                                        request.remote_addr if hasattr(request, 'remote_addr') else 'unknown',
                                        request.headers.get('User-Agent', 'Unknown'))
                
                return jsonify({
                    'status': 'success',
                    'message': f'Файл {filename} удален'
                })
                
            except Exception as e:
                error_msg = f"Ошибка удаления файла: {str(e)}"
                self.logger.log_error(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 500

        @self.app.route('/api/photos/clear', methods=['DELETE'])
        def clear_all_photos():
            """Удаление всех фотографий"""
            try:
                deleted_count = 0
                deleted_size = 0
                
                for filename in os.listdir(self.photos_dir):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        filepath = os.path.join(self.photos_dir, filename)
                        if os.path.isfile(filepath):
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_count += 1
                            deleted_size += file_size
                
                message = f"Удалено {deleted_count} файлов, освобождено {self.format_file_size(deleted_size)}"
                self.logger.log_web_action('clear_photos', 'success', message,
                                        request.remote_addr, request.headers.get('User-Agent', 'Unknown'))
                
                return jsonify({
                    'status': 'success',
                    'message': message,
                    'deleted_count': deleted_count,
                    'deleted_size': deleted_size,
                    'deleted_size_formatted': self.format_file_size(deleted_size)
                })
                
            except Exception as e:
                error_msg = f"Ошибка очистки фото: {str(e)}"
                self.logger.log_error(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 500

        # Статический маршрут для доступа к фото
        @self.app.route('/static/photos/<path:filename>')
        def serve_photo(filename):
            """Сервис для отдачи сохраненных фото"""
            try:
                photos_dir = os.path.join(current_dir, 'static', 'photos')
                filepath = os.path.join(photos_dir, filename)
                
                # Безопасность: проверяем, что файл находится в правильной директории
                if not os.path.abspath(filepath).startswith(os.path.abspath(photos_dir)):
                    return "Forbidden", 403
                
                if not os.path.exists(filepath):
                    return "Not Found", 404
                
                return self.app.send_static_file(f'photos/{filename}')
                
            except Exception as e:
                self.logger.log_error(f"Ошибка при отдаче фото {filename}: {e}")
                return "Internal Server Error", 500            


    def run(self):
        """Запуск сервера"""
        try:
            app_config = self.config['server']
            print(f"\n🚀 Запуск сервера на http://{app_config['host']}:{app_config['port']}")
            print("=" * 60)
            print("Нажмите Ctrl+C для остановки")
            print("=" * 60)
            
            self.app.run(
                host=app_config['host'],
                port=app_config['port'],
                debug=app_config['debug'],
                threaded=app_config['threaded']
            )
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Получен сигнал остановки...")
        except Exception as e:
            print(f"\n❌ Ошибка запуска сервера: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Очистка ресурсов"""
        print("\n🧹 Очистка ресурсов...")
        
        # Останавливаем стрим
        if hasattr(self, 'stream_active') and self.stream_active:
            self.stop_stream_internal()
        
        # Закрываем камеры
        if self.camera_type == 'csi':
            if hasattr(self, 'csi_manager'):
                self.csi_manager.close_current()
        else:
            with self.camera_lock:
                if hasattr(self, 'current_v4l2_camera') and self.current_v4l2_camera:
                    try:
                        self.current_v4l2_camera.release()
                        print("✅ USB камера освобождена")
                    except Exception as e:
                        print(f"⚠️  Ошибка при освобождении USB камеры: {e}")
        
        print("👋 Сервер остановлен")

    def get_stream_state_info(self):
        """Получение информации о состоянии стрима для диагностики"""
        camera_opened = False
        if self.camera_type == 'csi':
            camera_opened = self.current_picam2 is not None
        else:
            with self.camera_lock:
                camera_opened = self.current_v4l2_camera.isOpened() if self.current_v4l2_camera else False
        
        return {
            'stream_active': self.stream_active,
            'buffer_active': self.buffer_active,
            'frame_count': self.frame_count,
            'buffer_size': self.frame_buffer.qsize(),
            'buffer_maxsize': self.frame_buffer.maxsize,
            'camera_type': self.camera_type,
            'camera_opened': camera_opened,
            'thread_alive': self.buffer_thread.is_alive() if self.buffer_thread else False,
            'thread_id': self.buffer_thread.ident if self.buffer_thread else None,
            'active_streams': self.active_streams,
            'active_clients': len(self.active_clients)
        }        


def log_all_available_cameras(logger):
    """Логировать все доступные камеры в файл лога"""
    try:
        print("🔍 Сканирование доступных камер...")
        
        # Создаем CameraChecker
        checker = CameraChecker(logger=logger)
        
        # Если у логгера есть метод для записи, используем его
        cameras = checker.detect_cameras(max_devices=40)
        
        if not cameras:
            if hasattr(logger, 'log_warning'):
                logger.log_warning("❌ Видеокамеры не найдены в системе")
            else:
                logger.info("❌ Видеокамеры не найдены в системе")
            return
        
        # Логируем через стандартный метод CameraChecker
        checker.log_detection_results_with_fps(cameras)
        
        # Также выводим в консоль для наглядности
        print(f"📊 Найдено камер: {len(cameras)}")
        for i, cam in enumerate(cameras, 1):
            name = checker._get_camera_name(cam['device_path'])
            formats = ', '.join(cam['formats'])
            print(f"{i}. {cam['device_path']} - {name}")
            print(f"   Форматы: {formats}")
        
        print("✅ Сканирование завершено")
        
    except Exception as e:
        print(f"⚠️  Ошибка при сканировании камер: {e}")
        # Пробуем записать ошибку в лог
        if hasattr(logger, 'log_error'):
            logger.log_error(f"Ошибка при сканировании камер: {e}")
        elif hasattr(logger, 'error'):
            logger.error(f"Ошибка при сканировании камер: {e}")
        else:
            logger.info(f"ОШИБКА: {e}")

         
def main():
    parser = argparse.ArgumentParser(description='Flask Webcam Stream with YAML Configuration')
    parser.add_argument('--config', '-c', default='config_rpi.yaml', 
                       help='Путь к конфигурационному файлу YAML (по умолчанию: config_rpi.yaml)')
    args = parser.parse_args()
    
    # Создаем логгер
    logger = create_logger(args.config)
    
    # Загружаем конфигурацию
    # Функция возвращает СЛОВАРЬ
    config = load_config(args.config)
    
    # Логируем информацию о запуске
    logger.log_startup_info(config)
    
    print("=" * 60)
    print("🔍 Поиск рабочей камеры...")
    print("=" * 60)
    
    camera_info = test_camera_backends(config, logger)

    # ВРЕМЕННО ОТКЛЮЧАЕМ - вызывает конфликт с уже открытой камерой
    log_all_available_cameras(logger)   # ← ЗАКОММЕНТИРУЙТЕ ЭТУ СТРОКУ
    
    if camera_info is None:
        logger.log_error("НЕ НАЙДЕНА РАБОЧАЯ КАМЕРА!")
        print("\n❌ НЕ НАЙДЕНА РАБОЧАЯ КАМЕРА!")
        sys.exit(1)
    
    print("\n✅ Камера найдена и готова к работе!")
    
    # Создаем и запускаем стример
    try:
        streamer = CameraStreamer(config, logger, camera_info)

        # ✅ АВТОЗАПУСК СТРИМА ПРИ СТАРТЕ СЕРВЕРА
        if config.get('camera', {}).get('auto_start', False):
            print("🚀 Автозапуск стрима включен - запускаю...")
            logger.log_info("Автозапуск стрима включен в конфигурации")
            streamer.start_stream_internal()

        streamer.run()
    except Exception as e:
        print(f"❌ Ошибка создания CameraStreamer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()