"""
Модуль управления конфигурацией
"""
import os
import yaml
import json
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Создание необходимых директорий
        self._create_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка основного конфигурационного файла"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Загрузка конфигурации камеры
        camera_config_path = Path(config['camera']['config_file'])
        if camera_config_path.exists():
            with open(camera_config_path, 'r', encoding='utf-8') as f:
                camera_config = yaml.safe_load(f)
                config['camera'].update(camera_config['camera'])
        
        return config
    
    def _create_directories(self):
        """Создание необходимых директорий"""
        directories = [
            'logs',
            'config/camera/calibration',
            'models'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def load_model_position(self) -> Optional[Dict[str, Any]]:
        """Загрузка позиции модели из файла"""
        position_file = Path(self.config['model']['position_config'])
        
        if not position_file.exists():
            return None
        
        try:
            with open(position_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading model position: {e}")
            return None
    
    def save_model_position(self, params: Dict[str, Any]) -> bool:
        """Сохранение позиции модели"""
        position_file = Path(self.config['model']['position_config'])
        
        try:
            params_with_time = params.copy()
            params_with_time['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            with open(position_file, 'w', encoding='utf-8') as f:
                json.dump(params_with_time, f, indent=4)
            
            print(f"💾 Model position saved to {position_file}")
            return True
        except Exception as e:
            print(f"❌ Error saving model position: {e}")
            return False
    
    def slider_to_params(self, slider_values: Dict[str, int]) -> Dict[str, Any]:
        """Преобразование значений слайдеров в параметры модели"""
        params = {}
        
        # Масштаб
        if 'Scale_coarse' in slider_values:
            log_scale = -3 + (slider_values['Scale_coarse'] / 100) * 3.301
            params['scale'] = 10 ** log_scale
        
        if 'Scale_fine' in slider_values:
            fine_scale_factor = 1.0 + (slider_values['Scale_fine'] - 500) / 500.0 * 0.1
            if 'scale' in params:
                params['scale'] *= fine_scale_factor
        
        # Повороты
        params['rot_x'] = slider_values.get('Rot X_coarse', 180) - 180
        params['rot_y'] = slider_values.get('Rot Y_coarse', 180) - 180
        params['rot_z'] = slider_values.get('Rot Z_coarse', 180) - 180
        
        params['rot_x'] += (slider_values.get('Rot X_fine', 500) - 500) / 100.0 * 5
        params['rot_y'] += (slider_values.get('Rot Y_fine', 500) - 500) / 100.0 * 5
        params['rot_z'] += (slider_values.get('Rot Z_fine', 500) - 500) / 100.0 * 5
        
        # Смещения
        params['offset_x'] = (slider_values.get('Offset X_coarse', 500) - 500) / 100.0
        params['offset_y'] = (slider_values.get('Offset Y_coarse', 500) - 500) / 100.0
        params['offset_z'] = (slider_values.get('Offset Z_coarse', 500) - 500) / 100.0
        
        params['offset_x'] += (slider_values.get('Offset X_fine', 500) - 500) / 500.0 * 0.05
        params['offset_y'] += (slider_values.get('Offset Y_fine', 500) - 500) / 500.0 * 0.05
        params['offset_z'] += (slider_values.get('Offset Z_fine', 500) - 500) / 500.0 * 0.05
        
        # Режим отображения
        params['mode'] = slider_values.get('Mode', 1)
        
        return params
    
    def params_to_slider(self, params: Dict[str, Any]) -> Dict[str, int]:
        """Преобразование параметров модели в значения слайдеров"""
        slider_values = {}
        
        if 'scale' in params:
            scale = max(0.001, min(2.0, params['scale']))
            log_scale = np.log10(scale)
            slider_values['Scale_coarse'] = int((log_scale + 3) * 100 / 3.301)
            slider_values['Scale_fine'] = 500
        
        slider_values['Rot X_coarse'] = int(params.get('rot_x', 0) + 180)
        slider_values['Rot Y_coarse'] = int(params.get('rot_y', 0) + 180)
        slider_values['Rot Z_coarse'] = int(params.get('rot_z', 0) + 180)
        
        slider_values['Rot X_fine'] = 500
        slider_values['Rot Y_fine'] = 500
        slider_values['Rot Z_fine'] = 500
        
        slider_values['Offset X_coarse'] = int(params.get('offset_x', 0) * 100 + 500)
        slider_values['Offset Y_coarse'] = int(params.get('offset_y', 0) * 100 + 500)
        slider_values['Offset Z_coarse'] = int(params.get('offset_z', 0) * 100 + 500)
        
        slider_values['Offset X_fine'] = 500
        slider_values['Offset Y_fine'] = 500
        slider_values['Offset Z_fine'] = 500
        
        slider_values['Mode'] = int(params.get('mode', 1))
        
        return slider_values
