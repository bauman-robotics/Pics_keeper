
# 1 
Добавь поддержку yaml файлов. 
Создай yaml файл с конфигурацией запуска. 
Сделай выбор камеры в файле кофигурации

# 2 
Давай при старте писать логи в папку 002_logs -- в корне проекта
У нас есть готовая реализация логгера: 001_code/utils/logger.py
давай его перенесем в текущую версию нашего скрипта. 
и тоже его положим в папку utils 
004_code_flask_web_stream/utils

логи должны быть в том же формате. 
Пишем время запуска, параметры, с которыми запускается скрипт, 
выбранную камеру, разрешение ...

# 3 
Давай при старте в лог файл писать список доступных камер и их доступные разрешения и fps. 

# 4 
Если добавить команду lsusb  
 lsusb
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 001 Device 002: ID 046d:c328 Logitech, Inc. Corded Keyboard K280e
Bus 001 Device 003: ID 046d:c52b Logitech, Inc. Unifying Receiver
Bus 001 Device 012: ID 0c45:6340 Microdia Camera
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 003 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 003 Device 003: ID 046d:0825 Logitech, Inc. Webcam C270
Bus 004 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
можно увидеть названия камер, мы можем добавить в лог названия камер к устройствам 