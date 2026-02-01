import os
import subprocess

# Проверьте какие видеоустройства доступны
result = subprocess.run(['v4l2-ctl', '--list-devices'], 
                       capture_output=True, text=True)
print("Доступные устройства:")
print(result.stdout)

# Или через Python
import glob
video_devices = glob.glob('/dev/video*')
print(f"Найдены устройства: {video_devices}")
