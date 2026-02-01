# diagnostic.py
import os
import subprocess

def run_diagnostic():
    print("=== Диагностика системы Raspberry Pi ===")
    
    # 1. Проверка камеры
    print("\n1. Проверка камеры Raspberry Pi:")
    try:
        result = subprocess.run(['vcgencmd', 'get_camera'], 
                               capture_output=True, text=True)
        print(f"   {result.stdout}")
    except:
        print("   vcgencmd не найден")
    
    # 2. Проверка устройств
    print("\n2. Видеоустройства:")
    os.system("ls -la /dev/video*")
    
    # 3. Проверка v4l2
    print("\n3. Информация V4L2:")
    try:
        os.system("v4l2-ctl --list-devices")
    except:
        print("   v4l2-ctl не установлен")
    
    # 4. Проверка групп
    print("\n4. Права доступа:")
    print(f"   Текущий пользователь: {os.getenv('USER')}")
    os.system("groups")
    
    # 5. Проверка процессов
    print("\n5. Процессы, использующие камеру:")
    os.system("sudo lsof /dev/video* 2>/dev/null | head -20 || echo '   Нет доступа'")
    
    # 6. Проверка модулей ядра
    print("\n6. Загруженные модули ядра:")
    os.system("lsmod | grep -i video || echo '   Не найдены видео-модули'")
    
    print("\n=== Конец диагностики ===")

if __name__ == "__main__":
    run_diagnostic()
