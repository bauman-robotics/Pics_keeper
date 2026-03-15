"""
Менеджер кнопок
"""
import cv2
import numpy as np
from .button import Button


class ButtonManager:
    """Управление набором кнопок"""
    
    # Цвета кнопок
    COLORS = {
        'VIDEO ONLY': {'normal': (80, 80, 80), 'hover': (130, 130, 130),
                      'active': (50, 150, 50)},
        'MODEL': {'normal': (80, 80, 80), 'hover': (130, 130, 130),
                 'active': (50, 150, 50)},
        'SAVE': {'normal': (50, 150, 50), 'hover': (100, 255, 100)},
        'LOAD': {'normal': (50, 50, 150), 'hover': (100, 100, 255)},
        'RESET': {'normal': (150, 150, 50), 'hover': (255, 255, 100)},
        'ATTACH': {'normal': (150, 50, 150), 'hover': (255, 100, 255)},
        'REFINE': {'normal': (30, 80, 160), 'hover': (60, 140, 255),
                  'active': (0, 160, 220)},
        'FULL': {'normal': (100, 100, 100), 'hover': (150, 150, 150)},
        'EXIT': {'normal': (150, 50, 50), 'hover': (255, 100, 100)}
    }
    
    def __init__(self, ui_config, frame_width, frame_height):
        self.config = ui_config
        self.buttons_config = ui_config['buttons']
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        self.buttons = []
        self._create_buttons()
        
        # Словарь для быстрого доступа к кнопкам по тексту
        self.button_dict = {btn.text: btn for btn in self.buttons}
    
    def _create_buttons(self):
        """Создание всех кнопок"""
        btn_width = self.buttons_config['width']
        btn_height = self.buttons_config['height']
        margin = self.buttons_config['margin']
        
        # Вычисление начальной позиции
        n_buttons = len(self.COLORS)
        start_x = max(10, self.frame_width - 
                     (btn_width + margin) * n_buttons - 10)
        
        button_texts = list(self.COLORS.keys())
        
        for i, text in enumerate(button_texts):
            colors = self.COLORS[text]
            x = start_x + (btn_width + margin) * i
            y = 10
            
            # Определение начального состояния
            if text == "VIDEO ONLY":
                active = self.buttons_config.get('video_only_default', True)
            elif text == "MODEL":
                active = self.buttons_config.get('model_default', False)
            elif text == "REFINE":
                active = self.buttons_config.get('refine_default', False)
            else:
                active = False
            
            # Создание кнопки
            button = Button(
                x=x, y=y,
                width=btn_width, height=btn_height,
                text=text,
                color=colors['normal'],
                hover_color=colors['hover'],
                toggle=(text in ['VIDEO ONLY', 'MODEL', 'REFINE']),
                active_color=colors.get('active'),
                active=active
            )
            
            self.buttons.append(button)
    
    def update_hover(self, x, y):
        """Обновление состояния hover для всех кнопок"""
        for btn in self.buttons:
            btn.is_hovered = btn.is_inside(x, y)
    
    def handle_click(self, x, y):
        """Обработка клика мыши"""
        for btn in self.buttons:
            if btn.is_inside(x, y):
                if btn.toggle:
                    btn.toggle_state()
                return btn
        return None
    
    def draw_buttons(self, frame):
        """Отрисовка всех кнопок"""
        for btn in self.buttons:
            btn.draw(frame)
        return frame
    
    def get_button_state(self, button_text):
        """Получение состояния toggle кнопки"""
        btn = self.button_dict.get(button_text)
        if btn and btn.toggle:
            return btn.active
        return False
    
    def set_button_state(self, button_text, state):
        """Установка состояния toggle кнопки"""
        btn = self.button_dict.get(button_text)
        if btn and btn.toggle:
            btn.active = state
