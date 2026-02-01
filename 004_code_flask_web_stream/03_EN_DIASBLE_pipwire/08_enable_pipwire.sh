#!/bin/bash
# enable_pipewire.sh - Включение и восстановление PipeWire

# Что сделает скрипт:
#    Восстановит конфигурацию из бэкапа (если есть)
#    Размаскирует все сервисы
#    Включит автозапуск
#    Запустит все компоненты PipeWire
#    Проверит работоспособность

#=========================================
# Проверить, что процессы остановлены
#  ps aux | grep -E "(pipewire|wireplumber)"

# Проверить, что камеры свободны
#  sudo lsof /dev/video* 2>/dev/null || echo "Камеры свободны"

# Проверить статус сервисов
## systemctl --user status pipewire 2>/dev/null
#=========================================

echo "========================================"
echo "    ВКЛЮЧЕНИЕ И ВОССТАНОВЛЕНИЕ PIPEWIRE"
echo "========================================"

# Проверяем наличие бэкапа
BACKUP_DIR="$HOME/.pipewire_backup"
if [ ! -d "$BACKUP_DIR" ]; then
    echo ""
    echo "⚠ Бэкап не найден в $BACKUP_DIR"
    echo "Пытаемся восстановить стандартными методами..."
fi

# ============ 1. ВОССТАНОВЛЕНИЕ ИЗ БЭКАПА ============
if [ -d "$BACKUP_DIR" ] && [ -f "$BACKUP_DIR/restore_pipewire.sh" ]; then
    echo ""
    echo "[1/6] Восстановление из бэкапа..."
    cd "$BACKUP_DIR"
    ./restore_pipewire.sh
    cd - >/dev/null
else
    echo ""
    echo "[1/6] Восстановление стандартной конфигурации..."
    
    # Восстанавливаем D-Bus файлы
    for dbus_file in /usr/share/dbus-1/services/*pipewire*.disabled /usr/share/dbus-1/services/*wireplumber*.disabled; do
        if [ -f "$dbus_file" ]; then
            original="${dbus_file%.disabled}"
            sudo mv "$dbus_file" "$original" 2>/dev/null && \
            echo "  ✓ Восстановлен: $original"
        fi
    done
    
    # Восстанавливаем .desktop файлы
    for desktop_file in /etc/xdg/autostart/*pipewire*.disabled /etc/xdg/autostart/*wireplumber*.disabled; do
        if [ -f "$desktop_file" ]; then
            original="${desktop_file%.disabled}"
            sudo mv "$desktop_file" "$original" 2>/dev/null && \
            echo "  ✓ Восстановлен: $original"
        fi
    done
    
    # Восстанавливаем пользовательские .desktop файлы
    for desktop_file in $HOME/.config/autostart/*pipewire*.disabled $HOME/.config/autostart/*wireplumber*.disabled; do
        if [ -f "$desktop_file" ]; then
            original="${desktop_file%.disabled}"
            mv "$desktop_file" "$original" 2>/dev/null && \
            echo "  ✓ Восстановлен: $original"
        fi
    done
fi

# ============ 2. РАЗМАСКИРОВАНИЕ СЕРВИСОВ ============
echo ""
echo "[2/6] Размаскирование сервисов..."

SERVICES=(
    "pipewire"
    "pipewire-pulse" 
    "wireplumber"
    "pipewire.socket"
    "pipewire-pulse.socket"
)

for service in "${SERVICES[@]}"; do
    # Размаскируем user сервисы
    systemctl --user unmask $service 2>/dev/null && \
    echo "  ✓ Размаскирован (user): $service"
    
    # Размаскируем system сервисы (если есть)
    sudo systemctl unmask $service 2>/dev/null && \
    echo "  ✓ Размаскирован (system): $service"
done

# ============ 3. ВКЛЮЧЕНИЕ СЕРВИСОВ ============
echo ""
echo "[3/6] Включение сервисов..."

# Включаем сокеты (это важно для socket activation)
systemctl --user enable pipewire.socket pipewire-pulse.socket 2>/dev/null && \
echo "  ✓ Включены сокеты"

# Включаем основные сервисы
systemctl --user enable pipewire pipewire-pulse wireplumber 2>/dev/null && \
echo "  ✓ Включены основные сервисы"

# ============ 4. ПЕРЕЗАГРУЗКА DEMON ============
echo ""
echo "[4/6] Перезагрузка systemd демона..."

systemctl --user daemon-reload
echo "  ✓ Демон перезагружен"

# ============ 5. ЗАПУСК СЕРВИСОВ ============
echo "[5/6] Запуск сервисов..."

# Запускаем сокеты
systemctl --user start pipewire.socket pipewire-pulse.socket && \
echo "  ✓ Запущены сокеты"

# Запускаем основные сервисы
systemctl --user start pipewire pipewire-pulse wireplumber && \
echo "  ✓ Запущены основные сервисы"

# Альтернативный запуск, если systemd не сработал
sleep 2
if ! pgrep -f "pipewire" >/dev/null; then
    echo "  ⚠ PipeWire не запустился через systemd, запускаем вручную..."
    pipewire &
    sleep 1
    wireplumber &
    sleep 1
    pipewire-pulse &
fi

# ============ 6. ПРОВЕРКА ============
echo ""
echo "[6/6] Проверка работы..."

sleep 3

echo ""
echo "--- Статус процессов: ---"
if pgrep -f "pipewire" >/dev/null; then
    echo "✓ PipeWire запущен (PID: $(pgrep -f "pipewire"))"
else
    echo "✗ PipeWire не запущен"
fi

if pgrep -f "wireplumber" >/dev/null; then
    echo "✓ WirePlumber запущен (PID: $(pgrep -f "wireplumber"))"
else
    echo "✗ WirePlumber не запущен"
fi

echo "" 
echo "--- Статус сервисов: ---"
for service in pipewire pipewire-pulse wireplumber; do
    status=$(systemctl --user is-active $service 2>/dev/null || echo "unknown")
    enabled=$(systemctl --user is-enabled $service 2>/dev/null || echo "unknown")
    echo "  $service: активен=$status, автозапуск=$enabled"
done

echo "" 
echo "--- Проверка аудио: ---"
if pactl info 2>/dev/null | grep -q "PipeWire"; then
    echo "✓ Аудио работает через PipeWire"
else
    echo "⚠ Аудио может не работать"
    echo "  Попробуйте: pactl info"
fi

echo "" 
echo "--- Проверка камер: ---"
echo "Камеры теперь управляются через PipeWire"
echo "Для проверки: v4l2-ctl --list-devices"

echo "========================================"
echo "  ВКЛЮЧЕНИЕ ЗАВЕРШЕНО!"
echo "========================================"
echo "" 
echo "PipeWire должен быть полностью восстановлен."
echo "" 
echo "Если есть проблемы:"
echo "1. Проверьте процессы: ps aux | grep -E '(pipewire|wireplumber)'"
echo "2. Перезагрузитесь: sudo reboot"
echo "3. Проверьте аудио: speaker-test -t wav -c 2"
echo "" 
echo "Для отключения PipeWire используйте:"
echo "  ./disable_pipewire.sh"
