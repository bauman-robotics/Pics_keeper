from flask import Flask, Response
import io
import threading
from picamera2 import Picamera2
import libcamera
import time

app = Flask(__name__)

class GlobalShutterCamera:
    def __init__(self, media_device='/dev/media5'):
        self.media_device = media_device
        self.picam2 = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        
    def start(self):
        """Запуск камеры с глобальным затвором"""
        try:
            # Явно указываем медиа-устройство
            import os
            os.environ['LIBCAMERA_MEDIA_DEVICE'] = self.media_device
            
            self.picam2 = Picamera2()
            
            # Настройка для видео (глобальный затвор любит хорошее освещение)
            video_config = self.picam2.create_video_configuration(
                main={"size": (1456, 1088)},  # родное разрешение IMX296
                controls={
                    "FrameRate": 30,  # можно до 60 fps
                    "ExposureTime": 1000,  # 1ms выдержка (чем меньше, тем четче движение)
                    "AeEnable": True,  # автоэкспозиция для начала
                }
            )
            
            self.picam2.configure(video_config)
            self.picam2.start()
            self.running = True
            
            # Запускаем поток захвата кадров
            self.thread = threading.Thread(target=self._update_frame)
            self.thread.daemon = True
            self.thread.start()
            
            return True
        except Exception as e:
            print(f"Ошибка запуска Global Shutter: {e}")
            return False
    
    def _update_frame(self):
        """Фоновый захват кадров"""
        while self.running:
            try:
                # Захват кадра
                frame = self.picam2.capture_array()
                
                # Конвертация в JPEG для веб-потока
                from PIL import Image
                import numpy as np
                
                img = Image.fromarray(frame)
                with io.BytesIO() as output:
                    img.save(output, format='JPEG', quality=85)
                    jpeg_frame = output.getvalue()
                
                with self.lock:
                    self.frame = jpeg_frame
                    
                time.sleep(0.01)  # небольшая пауза
            except Exception as e:
                print(f"Ошибка захвата: {e}")
                time.sleep(0.1)
    
    def get_frame(self):
        """Получение последнего кадра"""
        with self.lock:
            return self.frame
    
    def stop(self):
        """Остановка камеры"""
        self.running = False
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()

# Создаем экземпляр камеры
global_cam = GlobalShutterCamera('/dev/media5')

@app.route('/global_stream')
def global_stream():
    """Видеопоток с Global Shutter камеры"""
    def generate():
        while True:
            frame = global_cam.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/global_snapshot')
def global_snapshot():
    """Один снимок с Global Shutter"""
    try:
        # Используем libcamera-still для снимка
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_file = f.name
        
        # Делаем снимок
        result = subprocess.run([
            'libcamera-still',
            '--device', '/dev/media5',
            '--output', temp_file,
            '--width', '1456',
            '--height', '1088',
            '--nopreview'
        ], capture_output=True)
        
        if result.returncode == 0:
            with open(temp_file, 'rb') as f:
                img_data = f.read()
            import os
            os.unlink(temp_file)
            return Response(img_data, mimetype='image/jpeg')
        else:
            return "Ошибка съемки", 500
    except Exception as e:
        return str(e), 500

@app.route('/start_global')
def start_global():
    """Запуск глобальной камеры"""
    if global_cam.start():
        return "Global Shutter камера запущена"
    return "Ошибка запуска", 500

@app.route('/stop_global')
def stop_global():
    """Остановка глобальной камеры"""
    global_cam.stop()
    return "Global Shutter камера остановлена"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
