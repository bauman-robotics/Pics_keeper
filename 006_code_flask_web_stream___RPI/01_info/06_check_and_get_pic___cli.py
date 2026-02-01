import cv2
import warnings
import sys
import os
import time
import threading
import select
import termios
import tty
import signal

class CameraCapture:
    def __init__(self):
        self.running = True
        self.camera_index = None
        self.cap = None
        self.current_frame = None
        self.preview_window = "Camera Preview"
        
        # Настройка обработки Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Обработчик Ctrl+C"""
        print("\n\nЗавершение работы...")
        self.running = False
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)
    
    def detect_cameras(self):
        """Обнаруживает доступные камеры"""
        print("\n" + "="*50)
        print("ОБНАРУЖЕНИЕ КАМЕР...")
        print("="*50)
        
        # Подавляем предупреждения от OpenCV
        warnings.filterwarnings('ignore')
        
        # Сохраняем оригинальный stderr
        original_stderr = sys.stderr
        
        try:
            # Отключаем вывод ошибок в stderr
            sys.stderr = open(os.devnull, 'w')
            
            available_cameras = []
            
            # Проверяем камеры от 0 до 10
            for i in range(10):
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                    if cap.isOpened():
                        # Пробуем получить кадр
                        ret, frame = cap.read()
                        if ret:
                            # Получаем информацию о камере
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            
                            # Проверяем поддержку HD
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                            hd_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            hd_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            
                            available_cameras.append({
                                'index': i,
                                'device': f'/dev/video{i}',
                                'width': width,
                                'height': height,
                                'fps': fps if fps > 0 else 'N/A',
                                'supports_hd': (hd_width >= 1280 and hd_height >= 720)
                            })
                            print(f"  Найдена камера: /dev/video{i} ({width}x{height})")
                        cap.release()
                except:
                    continue
            
            return available_cameras
            
        finally:
            # Восстанавливаем stderr
            sys.stderr = original_stderr
    
    def print_camera_menu(self, cameras):
        """Выводит меню выбора камеры"""
        print("\n" + "="*50)
        print("ВЫБЕРИТЕ КАМЕРУ:")
        print("="*50)
        
        if not cameras:
            print("  Камеры не обнаружены!")
            return
        
        for i, cam in enumerate(cameras, 1):
            hd_mark = " [HD]" if cam['supports_hd'] else ""
            print(f"  {i}. /dev/video{cam['index']}{hd_mark}")
            print(f"     Разрешение: {cam['width']}x{cam['height']}, FPS: {cam['fps']}")
        
        print("\n" + "="*50)
        print("УПРАВЛЕНИЕ:")
        print("  [1-9] - Выбрать камеру")
        print("  [s]   - Сделать снимок")
        print("  [q]   - Выход")
        print("  [c]   - Сменить камеру")
        print("="*50)
    
    def wait_for_key(self):
        """Ожидает нажатия клавиши без блокировки"""
        try:
            # Настраиваем терминал для немедленного чтения
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
            # Проверяем, есть ли данные для чтения
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1)
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                return key
            
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            return None
            
        except:
            return None
    
    def open_camera(self, camera_index):
        """Открывает камеру без GUI для SSH"""
        print(f"Открытие камеры /dev/video{camera_index}...")
        
        # Используем CAP_V4L2 для Linux
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            print(f"Ошибка: не удалось открыть камеру /dev/video{camera_index}")
            return False
        
        try:
            # Устанавливаем HD разрешение если поддерживается
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Даем камере время на инициализацию
            time.sleep(1)
            
            # Получаем текущие настройки
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            print(f"✓ Камера открыта")
            print(f"  Разрешение: {width}x{height}")
            if fps > 0:
                print(f"  FPS: {fps:.1f}")
            
            return True
            
        except Exception as e:
            print(f"Ошибка при открытии камеры: {e}")
            return False
    
    def capture_snapshot(self):
        """Делает снимок без GUI"""
        if self.cap is None or not self.cap.isOpened():
            print("Ошибка: камера не открыта")
            return False
        
        print("Захват кадра...")
        
        try:
            # Читаем несколько кадров для очистки буфера
            for i in range(5):
                self.cap.read()
            
            # Захватываем основной кадр
            ret, frame = self.cap.read()
            
            if not ret:
                print("Ошибка: не удалось получить кадр")
                return False
            
            # Генерируем имя файла
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{self.camera_index}_{timestamp}.jpg"
            
            # Сохраняем изображение
            cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # Получаем информацию о файле
            file_size = os.path.getsize(filename) / 1024  # в КБ
            
            print(f"\n✓ Снимок сохранен: {filename}")
            print(f"  Размер изображения: {frame.shape[1]}x{frame.shape[0]}")
            print(f"  Размер файла: {file_size:.1f} KB")
            
            return True
            
        except Exception as e:
            print(f"Ошибка при захвате: {e}")
            return False
    
    def preview_camera(self):
        """Запускает предпросмотр камеры"""
        print("\nЗапуск предпросмотра...")
        print("Нажмите [s] для снимка, [q] для выхода, [c] для смены камеры")
        
        while self.running and self.cap is not None and self.cap.isOpened():
            # Читаем кадр
            ret, frame = self.cap.read()
            if not ret:
                print("Ошибка чтения кадра")
                break
            
            # Показываем кадр
            cv2.imshow(self.preview_window, frame)
            
            # Проверяем нажатие клавиш в OpenCV
            key = cv2.waitKey(1) & 0xFF
            
            # Также проверяем нажатие в терминале
            terminal_key = self.wait_for_key()
            
            # Обработка клавиш
            if key == ord('q') or terminal_key == 'q':
                print("\nВыход из предпросмотра...")
                break
            elif key == ord('s') or terminal_key == 's':
                self.capture_snapshot()
            elif terminal_key == 'c':  # Только из терминала
                print("\nВозврат к выбору камеры...")
                cv2.destroyWindow(self.preview_window)
                return 'change_camera'
            
            # Проверяем закрытие окна
            if cv2.getWindowProperty(self.preview_window, cv2.WND_PROP_VISIBLE) < 1:
                break
        
        cv2.destroyWindow(self.preview_window)
        return 'exit'
    
    def interactive_mode(self):
        """Основной интерактивный режим"""
        print("\n" + "="*50)
        print("ПРОГРАММА ЗАХВАТА С КАМЕРЫ")
        print("="*50)
        
        # Обнаруживаем камеры
        cameras = self.detect_cameras()
        
        if not cameras:
            print("\nКамеры не обнаружены!")
            print("Проверьте подключение камер и попробуйте снова.")
            return
        
        while self.running:
            # Показываем меню
            self.print_camera_menu(cameras)
            
            # Ожидаем выбора камеры
            print("\nВыберите камеру (1-9) или 'q' для выхода: ", end='', flush=True)
            
            try:
                # Ждем ввода пользователя
                choice = input().strip().lower()
                
                if choice == 'q':
                    print("\nВыход из программы...")
                    break
                
                # Проверяем, что ввод - цифра
                if choice.isdigit():
                    cam_num = int(choice)
                    
                    if 1 <= cam_num <= len(cameras):
                        selected_cam = cameras[cam_num - 1]
                        self.camera_index = selected_cam['index']
                        
                        # Открываем камеру
                        if self.open_camera(self.camera_index):
                            # Сразу делаем снимок без предпросмотра
                            self.capture_snapshot()
                            
                            # Закрываем камеру
                            if self.cap is not None:
                                self.cap.release()
                                self.cap = None
                            
                            # Спрашиваем, сделать еще один снимок или выйти
                            print("\nСделать еще один снимок? (y/n): ", end='', flush=True)
                            another = input().strip().lower()
                            if another != 'y':
                                break
                            # Если 'y', продолжаем цикл (вернемся к выбору камеры)
                        else:
                            print("Не удалось открыть камеру. Попробуйте другую.")
                    else:
                        print(f"Ошибка: выберите число от 1 до {len(cameras)}")
                    
            except KeyboardInterrupt:
                print("\n\nПрограмма завершена пользователем.")
                break
            except Exception as e:
                print(f"\nОшибка: {e}")
                continue
        
        # Завершаем работу
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        print("\nПрограмма завершена.")
    
    def run(self):
        """Основной метод запуска"""
        try:
            self.interactive_mode()
        except Exception as e:
            print(f"\nКритическая ошибка: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
            cv2.destroyAllWindows()


def main():
    """Точка входа в программу"""
    print("Запуск программы захвата с веб-камер...")
    
    # Создаем и запускаем приложение
    app = CameraCapture()
    app.run()


if __name__ == "__main__":
    main()