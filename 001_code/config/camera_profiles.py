#!/usr/bin/env python3
"""
Профили камер и константы для Pics_keeper
"""

# ПАРАМЕТРЫ КАМЕР
CAMERA_PROFILES = {
    'imx708': {
        'name': 'IMX708 (RPi Camera Module 3)',
        'full_resolution': (4608, 2592),
        'sensor_size': (4.55, 3.42),
        'pixel_size': 1.0,
        'focal_length': 3.04,
    },
    'imx415': {
        'name': 'Sony IMX415',
        'full_resolution': (3864, 2192),        
        'sensor_size': (5.568, 3.132),
        'pixel_size': 1.45,
        'focal_length': 3.95,
    },
    'ov5647': {
        'name': 'OV5647 (RPi Camera Module v1/v2)',
        'full_resolution': (2592, 1944),
        'sensor_size': (3.68, 2.76),
        'pixel_size': 1.4,
        'focal_length': 3.6,
    },
    'local_web': {
        'name': 'Local Web Camera',
        'full_resolution': (1280, 960),
        'sensor_size': (3.2, 2.4),
        'pixel_size': 2.5,
        'focal_length': 3.6,
    }
}

# ПАРАМЕТРЫ ПО УМОЛЧАНИЮ
# imx708 -0    imx415 -1    ov5647    local_web -2
#DEFAULT_CAMERA_TYPE = 'imx708'  
#DEFAULT_CAMERA_TYPE = 'imx415'
DEFAULT_CAMERA_TYPE = 'local_web'

# ПАРАМЕТРЫ СЪЕМКИ
DEFAULT_DELAY = 0
DEFAULT_COUNT = 20
DEFAULT_OUTPUT_DIR = 'calibration_images'
DEFAULT_JPEG_QUALITY = 95

# ПАРАМЕТРЫ КОНТРОЛЯ УГЛОВ (только для съемки)
MAX_ACCEPTABLE_ANGLE = 45
WARNING_ANGLE = 30
ASPECT_RATIO_TOLERANCE = 0.15

# ПАРАМЕТРЫ ПРЕДПРОСМОТРА
DEFAULT_PREVIEW_ENABLED = False

# ПАРАМЕТРЫ ЭКСПОЗИЦИИ ПО УМОЛЧАНИЮ
DEFAULT_EXPOSURE_TIME = 40000         # Выдержка в микросекундах (40ms)
DEFAULT_ANALOGUE_GAIN = 2.0           # Аналоговое усиление
DEFAULT_DIGITAL_GAIN = 1.0            # Цифровое усиление
DEFAULT_AE_ENABLE = False             # Автоэкспозиция для съемки (False=выкл)
DEFAULT_AWB_ENABLE = True             # Автобаланс белого
DEFAULT_NOISE_REDUCTION_MODE = 2      # Режим шумоподавления (2=высокое качество)

# ПАРАМЕТРЫ ФОКУСИРОВКИ ПО УМОЛЧАНИЮ
DEFAULT_AF_ENABLE = False             # Автофокус (False=выкл для калибровки)
DEFAULT_LENS_POSITION = 0.5           # Позиция линзы (1.0=бесконечность для IMX415)
DEFAULT_AF_MODE = 0                   # Режим автофокуса
DEFAULT_AF_RANGE = 0                  # Диапазон фокусировки

# ПАРАМЕТРЫ СТРИМА (ЭКСПОЗИЦИЯ)
DEFAULT_STREAM_AE_ENABLE = True       # Автоэкспозиция для стрима (True=вкл)
DEFAULT_STREAM_EXPOSURE_TIME = 40000  # Стартовая выдержка для стрима
DEFAULT_STREAM_ANALOGUE_GAIN = 2.0    # Стартовое усиление для стрима
DEFAULT_STREAM_NOISE_REDUCTION = 1    # Режим шумоподавления для стрима (1=быстрый)

# ПАРАМЕТРЫ СТРИМА ПО УМОЛЧАНИЮ
DEFAULT_STREAM_ENABLED = True
DEFAULT_STREAM_PORT = 8080
DEFAULT_STREAM_FPS = 30               # Выше FPS для меньшей задержки
DEFAULT_STREAM_QUALITY = 50
DEFAULT_STREAM_ANALYSIS = False       # Отключить анализ по умолчанию для скорости
DEFAULT_STREAM_LOW_LATENCY = True     # Режим низкой задержки

# ПАРАМЕТРЫ РАЗРЕШЕНИЯ
full_resolution_IMX708_w = 4608
full_resolution_IMX708_h = 2592
full_resolution_IMX415_w = 3864
full_resolution_IMX415_h = 2192

# ПАРАМЕТРЫ РАЗРЕШЕНИЯ ПО УМОЛЧАНИЮ
DEFAULT_RESOLUTION = 'full'           # 'full' или 'stream'
DEFAULT_STREAM_WIDTH = 1280           # Ширина стрима по умолчанию
DEFAULT_STREAM_HEIGHT = 720           # Высота стрима по умолчанию

STREAM_TYPE = '1280x720'

if STREAM_TYPE == 'full_resolution':
    if DEFAULT_CAMERA_TYPE == 'imx415':
        DEFAULT_STREAM_WIDTH = full_resolution_IMX415_w           # Ширина стрима по умолчанию  imx415
        DEFAULT_STREAM_HEIGHT = full_resolution_IMX415_h           # Высота стрима по умолчанию
    else: 
        DEFAULT_STREAM_WIDTH = full_resolution_IMX708_w           # Ширина стрима по умолчанию  imx708
        DEFAULT_STREAM_HEIGHT = full_resolution_IMX708_h           # Высота стрима по умолчанию  
elif STREAM_TYPE == '1280x720':
    DEFAULT_STREAM_WIDTH = 1280           # Ширина стрима по умолчанию
    DEFAULT_STREAM_HEIGHT = 720           # Высота стрима по умолчанию 
elif STREAM_TYPE == '640x480':
    DEFAULT_STREAM_WIDTH = 640           # Ширина стрима по умолчанию
    DEFAULT_STREAM_HEIGHT = 480           # Высота стрима по умолчанию   

def get_camera_profile(camera_type):
    """Получение профиля камеры по типу"""
    return CAMERA_PROFILES.get(camera_type, CAMERA_PROFILES['imx708'])

def get_default_settings():
    """Получение настроек по умолчанию"""
    return {
        'camera_type': DEFAULT_CAMERA_TYPE,
        'stream_width': DEFAULT_STREAM_WIDTH,
        'stream_height': DEFAULT_STREAM_HEIGHT,
        'stream_fps': DEFAULT_STREAM_FPS,
        'stream_quality': DEFAULT_STREAM_QUALITY,
        'stream_analysis': DEFAULT_STREAM_ANALYSIS,
        'stream_low_latency': DEFAULT_STREAM_LOW_LATENCY,
        'delay': DEFAULT_DELAY,
        'count': DEFAULT_COUNT,
        'output_dir': DEFAULT_OUTPUT_DIR,
        'jpeg_quality': DEFAULT_JPEG_QUALITY,
        'max_angle': MAX_ACCEPTABLE_ANGLE,
        'warn_angle': WARNING_ANGLE,
        'force_capture': False,
        'exposure_time': DEFAULT_EXPOSURE_TIME,
        'analogue_gain': DEFAULT_ANALOGUE_GAIN,
        'ae_enable': DEFAULT_AE_ENABLE,
        'af_enable': DEFAULT_AF_ENABLE,
        'lens_position': DEFAULT_LENS_POSITION,
        'preview_enabled': DEFAULT_PREVIEW_ENABLED,
        'debug': False
    }