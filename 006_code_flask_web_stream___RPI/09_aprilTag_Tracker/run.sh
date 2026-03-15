#!/bin/bash
# Скрипт запуска AprilTag Tracker

# Получаем путь к директории скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Переходим в директорию проекта
cd "$SCRIPT_DIR"

# Активация виртуального окружения
source venv/bin/activate

# Настройка переменных окружения для Raspberry Pi
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1  # если проблемы с OpenGL

# Добавляем путь к Python модулям
export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}"

# Запуск
echo "🚀 Starting AprilTag Tracker..."
python3 src/main.py

# Деактивация при выходе
deactivate