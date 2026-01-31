#!/bin/bash
echo "=== Сравнение форматов видеокамер ==="
echo ""

for dev in /dev/video0 /dev/video1 /dev/video2 /dev/video3; do
    echo "--- $dev ---"
    # Пробуем получить базовую информацию
    if v4l2-ctl -d $dev --info > /dev/null 2>&1; then
        echo "Тип: Video Capture"
        # Получаем список форматов
        echo "Форматы:"
        v4l2-ctl -d $dev --list-formats 2>/dev/null | grep -o "'.*'" | sed 's/^/  /'
        
        # Проверяем доступные разрешения для первого формата
        echo "Доступные разрешения (для первого формата):"
        v4l2-ctl -d $dev --list-formats-ext 2>/dev/null | grep "Size:" | head -3
    else
        echo "Устройство недоступно или ошибка"
    fi
    echo ""
done
