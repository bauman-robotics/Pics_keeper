"""
Управление отображением
"""
import cv2
import numpy as np
import tkinter as tk


class DisplayManager:
    """Менеджер отображения кадров"""
    
    def __init__(self, config):
        self.config = config
        self.window_name = 'AprilTag Camera View'
        
        # Определение размера экрана
        self._get_screen_size()
        
        # Создание окна
        self._create_window()
        
        # Режим fullscreen
        self.fullscreen = False
    
    def _get_screen_size(self):
        """Получение размера экрана"""
        try:
            root = tk.Tk()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            
            scale = self.config.get('scale', 0.95)
            self.display_width = int(screen_width * scale)
            self.display_height = int(screen_height * scale)
            
            print(f"\n🖥️ SCREEN RESOLUTION")
            print(f"{'='*50}")
            print(f"   Screen: {screen_width}x{screen_height}")
            print(f"   Window: {self.display_width}x{self.display_height} "
                  f"({scale*100:.0f}%)")
            
        except:
            self.display_width = 1280
            self.display_height = 720
            print(f"\n⚠️ Using default: {self.display_width}x{self.display_height}")
    
    def _create_window(self):
        """Создание окна отображения"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.display_width, self.display_height)
        cv2.moveWindow(self.window_name, 0, 0)
    
    def resize_frame(self, frame):
        """
        Масштабирование кадра под размер окна с сохранением пропорций
        
        Returns:
            display_frame, scale_x, scale_y, x_offset, y_offset
        """
        h, w = frame.shape[:2]
        
        if h == 0 or w == 0:
            return frame, 1.0, 1.0, 0, 0
        
        aspect = w / h
        target_aspect = self.display_width / self.display_height
        
        if aspect > target_aspect:
            new_w = self.display_width
            new_h = int(self.display_width / aspect)
        else:
            new_h = self.display_height
            new_w = int(self.display_height * aspect)
        
        new_w = max(1, new_w)
        new_h = max(1, new_h)
        
        y_offset = (self.display_height - new_h) // 2
        x_offset = (self.display_width - new_w) // 2
        
        frame_resized = cv2.resize(frame, (new_w, new_h))
        
        display_frame = np.zeros((self.display_height, self.display_width, 3),
                                 dtype=np.uint8)
        display_frame[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame_resized
        
        scale_x = new_w / w
        scale_y = new_h / h
        
        return display_frame, scale_x, scale_y, x_offset, y_offset
    
    def show_frame(self, frame):
        """Отображение кадра"""
        display_frame, scale_x, scale_y, x_offset, y_offset = self.resize_frame(frame)
        cv2.imshow(self.window_name, display_frame)
        
        return display_frame, scale_x, scale_y, x_offset, y_offset
    
    def toggle_fullscreen(self):
        """Переключение полноэкранного режима"""
        self.fullscreen = not self.fullscreen
        
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN,
                                 cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN,
                                 cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, self.display_width, self.display_height)
            cv2.moveWindow(self.window_name, 0, 0)
