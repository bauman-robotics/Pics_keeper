"""
Класс кнопки для отображения на кадре
"""
import cv2


class Button:
    """Интерактивная кнопка на изображении"""
    
    def __init__(self, x, y, width, height, text,
                 color=(100, 100, 200),
                 hover_color=(150, 150, 255),
                 toggle=False,
                 active_color=None,
                 active=False):
        
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        self.toggle = toggle
        self.active = active
        
        if active_color:
            self.active_color = active_color
        else:
            self.active_color = (50, 200, 50)  # зеленый по умолчанию
    
    def draw(self, frame):
        """Отрисовка кнопки на кадре"""
        # Выбор цвета
        if self.toggle and self.active:
            color = self.active_color
        elif self.is_hovered:
            color = self.hover_color
        else:
            color = self.color
        
        # Заливка
        cv2.rectangle(frame, (self.x, self.y),
                     (self.x + self.width, self.y + self.height),
                     color, -1)
        
        # Рамка
        cv2.rectangle(frame, (self.x, self.y),
                     (self.x + self.width, self.y + self.height),
                     (255, 255, 255), 2)
        
        # Текст
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, 2)[0]
        text_x = self.x + (self.width - text_size[0]) // 2
        text_y = self.y + (self.height + text_size[1]) // 2
        
        cv2.putText(frame, self.text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                   (255, 255, 255), 2)
    
    def is_inside(self, x, y):
        """Проверка, находится ли точка внутри кнопки"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)
    
    def toggle_state(self):
        """Переключение состояния (для toggle кнопок)"""
        if self.toggle:
            self.active = not self.active
        return self.active
