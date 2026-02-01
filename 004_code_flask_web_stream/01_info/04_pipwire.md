# pipwire 
sudo lsof /dev/video* 2>/dev/null | head -20 || echo '   Нет доступа'

COMMAND    PID USER  FD   TYPE DEVICE SIZE/OFF NODE NAME
pipewire  1140   pi  76u   CHR  81,21      0t0  752 /dev/video4
pipewire  1140   pi  77u   CHR  81,24      0t0  755 /dev/video7
pipewire  1140   pi  78u   CHR  81,23      0t0  754 /dev/video6
pipewire  1140   pi  79u   CHR  81,18      0t0  749 /dev/video1
pipewire  1140   pi  80u   CHR   81,0      0t0  687 /dev/video20
pipewire  1140   pi  81u   CHR   81,3      0t0  690 /dev/video23
pipewire  1140   pi  82u   CHR   81,4      0t0  691 /dev/video24
pipewire  1140   pi  83u   CHR   81,7      0t0  694 /dev/video27
pipewire  1140   pi  84u   CHR   81,1      0t0  688 /dev/video21
pipewire  1140   pi  85u   CHR   81,5      0t0  692 /dev/video25
pipewire  1140   pi  86u   CHR   81,2      0t0  689 /dev/video22
pipewire  1140   pi  87u   CHR   81,6      0t0  693 /dev/video26
pipewire  1140   pi  95u   CHR  81,35      0t0  787 /dev/video14
pipewire  1140   pi  96u   CHR  81,38      0t0  790 /dev/video17
pipewire  1140   pi  97u   CHR  81,37      0t0  789 /dev/video16
pipewire  1140   pi  98u   CHR   81,8      0t0  696 /dev/video28
pipewire  1140   pi  99u   CHR  81,11      0t0  699 /dev/video31
pipewire  1140   pi 100u   CHR  81,12      0t0  700 /dev/video32
pipewire  1140   pi 101u   CHR  81,15      0t0  703 /dev/video35

# PipeWire — это мультимедийный сервер нового поколения для Linux, 
который заменяет старые системы PulseAudio (для звука) и частично JACK/ALSA. 
Он также управляет видеоустройствами (камерами), обеспечивая унифицированный доступ к аудио- и видеопотокам.


С PipeWire:
Ваш скрипт (Picamera2) → PipeWire → libcamera → /dev/video*

БЕЗ PipeWire:
Ваш скрипт (Picamera2) → libcamera → /dev/video*  [ПРЯМОЙ ДОСТУП!]

1. Picamera2 использует libcamera напрямую
Ваш скрипт использует Picamera2 из библиотеки libcamera-python, которая:
    Обращается напрямую к /dev/video* через V4L2
    Не зависит от PipeWire
    Имеет собственные драйверы и API

🚀 Преимущества отключения PipeWire для вашего скрипта:
1. Меньше задержки (Latency):
# С PipeWire: ~50-100ms дополнительной задержки
# Без PipeWire: прямая задержка ~10-30ms    

2. Стабильность соединения:
    Нет конфликтов за устройства
    Предсказуемый доступ к камере
    Меньше точек отказа

3. Проще отладка:
# Просто смотрите, кто использует камеру
sudo fuser /dev/video0