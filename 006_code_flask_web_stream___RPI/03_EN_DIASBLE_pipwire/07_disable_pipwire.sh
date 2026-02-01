#!/bin/bash
# disable_pipewire.sh - Полное отключение PipeWire с сохранением состояния

# Что сделает скрипт:
#    Сохранит текущую конфигурацию в ~/.pipewire_backup/
#    Остановит все процессы PipeWire
#    Отключит автозапуск на всех уровнях
#    Заблокирует D-Bus и XDG активации
#    Создаст скрипт восстановления
#    Освободит камеры

#=========================================
# Проверить, что процессы остановлены
#  ps aux | grep -E "(pipewire|wireplumber)"

# Проверить, что камеры свободны
#  sudo lsof /dev/video* 2>/dev/null || echo "Камеры свободны"

# Проверить статус сервисов
## systemctl --user status pipewire 2>/dev/null
#=========================================

echo "========================================"
echo "    ПОЛНОЕ ОТКЛЮЧЕНИЕ PIPEWIRE"
echo "========================================"

# Создаем директорию для бэкапа
BACKUP_DIR="$HOME/.pipewire_backup"
mkdir -p "$BACKUP_DIR"
echo "Бэкап конфигурации в: $BACKUP_DIR"

# ============ 1. СОХРАНЕНИЕ ТЕКУЩЕГО СОСТОЯНИЯ ============
echo ""
echo "[1/7] Сохранение текущего состояния..."

# Сохраняем статус сервисов
systemctl --user list-unit-files --all | grep -E "(pipewire|wireplumber|pulse)" > "$BACKUP_DIR/services_status.txt" 2>/dev/null

# Сохраняем активные состояния
echo "ENABLED_SERVICES:" > "$BACKUP_DIR/enabled_services.txt"
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    if systemctl --user is-enabled $service >/dev/null 2>&1; then
        echo "$service" >> "$BACKUP_DIR/enabled_services.txt"
    fi
done

# Сохраняем конфигурационные файлы
echo ""
echo "[2/7] Бэкап конфигурационных файлов..."

CONFIG_FILES=(
    "/usr/share/dbus-1/services/org.freedesktop.PipeWire.service"
    "/usr/share/dbus-1/services/org.freedesktop.PipeWire.Pulse.service"
    "/usr/lib/systemd/user/pipewire.service"
    "/usr/lib/systemd/user/pipewire-pulse.service"
    "/usr/lib/systemd/user/wireplumber.service"
    "/usr/lib/systemd/user/pipewire.socket"
    "/usr/lib/systemd/user/pipewire-pulse.socket"
    "/etc/xdg/autostart/pipewire.desktop"
    "/etc/xdg/autostart/wireplumber.desktop"
    "/etc/xdg/autostart/pipewire-pulse.desktop"
    "$HOME/.config/systemd/user/pipewire.service"
    "$HOME/.config/autostart/pipewire.desktop"
)

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/" 2>/dev/null && echo "  ✓ $file" || echo "  ✗ Ошибка: $file"
    fi
done

# ============ 2. ОСТАНОВКА ПРОЦЕССОВ ============
echo ""
echo "[3/7] Остановка процессов..."

# Останавливаем user сервисы
systemctl --user stop pipewire pipewire-pulse wireplumber 2>/dev/null
systemctl --user stop pipewire.socket pipewire-pulse.socket 2>/dev/null

# Принудительно убиваем процессы
sudo pkill -9 -f pipewire 2>/dev/null
sudo pkill -9 -f wireplumber 2>/dev/null
sudo pkill -9 -f pipewire-pulse 2>/dev/null

# ============ 3. ОТКЛЮЧЕНИЕ АВТОЗАПУСКА ============
echo ""
echo "[4/7] Отключение автозапуска..."

# Отключаем и маскируем user сервисы
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    systemctl --user disable $service 2>/dev/null
    systemctl --user mask $service 2>/dev/null
done

# Отключаем system сервисы (если есть)
sudo systemctl disable pipewire pipewire-pulse wireplumber 2>/dev/null
sudo systemctl mask pipewire pipewire-pulse wireplumber 2>/dev/null

# ============ 4. БЛОКИРОВКА D-BUS АКТИВАЦИИ ============
echo ""
echo "[5/7] Блокировка D-Bus активации..."

# Переименовываем D-Bus файлы
for dbus_file in /usr/share/dbus-1/services/*pipewire* /usr/share/dbus-1/services/*wireplumber*; do
    if [ -f "$dbus_file" ]; then
        sudo mv "$dbus_file" "${dbus_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $(basename "$dbus_file")"
    fi
done

# ============ 5. БЛОКИРОВКА XDG AUTOSTART ============
echo ""
echo "[6/7] Блокировка XDG autostart..."

# Глобальные .desktop файлы
for desktop_file in /etc/xdg/autostart/*pipewire* /etc/xdg/autostart/*wireplumber*; do
    if [ -f "$desktop_file" ]; then
        sudo mv "$desktop_file" "${desktop_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $(basename "$desktop_file")"
    fi
done

# Пользовательские .desktop файлы
for desktop_file in "$HOME/.config/autostart/"*pipewire* "$HOME/.config/autostart/"*wireplumber*; do
    if [ -f "$desktop_file" ]; then
        mv "$desktop_file" "${desktop_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $(basename "$desktop_file")"
    fi
done

# ============ 6. ПРОВЕРКА РЕЗУЛЬТАТА ============
echo ""
echo "[7/7] Проверка результата..."

sleep 2

echo ""
echo "--- Текущие процессы PipeWire: ---"
if pgrep -f "pipewire|wireplumber" >/dev/null; then
    echo "⚠ Некоторые процессы все еще активны:"
    ps aux | grep -E "(pipewire|wireplumber)" | grep -v grep
    echo "Принудительное завершение..."
    sudo pkill -KILL -f "pipewire|wireplumber"
else
    echo "✓ Все процессы PipeWire остановлены"
fi

echo ""
echo "--- Статус сервисов: ---"
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    status=$(systemctl --user is-active "$service" 2>/dev/null || echo "inactive")
    enabled=$(systemctl --user is-enabled "$service" 2>/dev/null || echo "disabled")
    echo "  $service: статус=$status, автозапуск=$enabled"
done

echo ""
echo "--- Доступ к камерам: ---"
if sudo lsof /dev/video* 2>/dev/null | grep -q "pipewire\|wireplumber"; then
    echo "⚠ PipeWire все еще держит камеры"
    echo "Освобождаем камеры..."
    sudo fuser -k /dev/video* 2>/dev/null
else
    echo "✓ Камеры свободны"
fi

# ============ 7. СОЗДАНИЕ СКРИПТА ВОССТАНОВЛЕНИЯ ============
cat > "$BACKUP_DIR/restore_pipewire.sh" << 'EOF'
#!/bin/bash
# Скрипт восстановления PipeWire (запускать из директории с бэкапом)

echo "Восстановление PipeWire..."

# Проверяем, что мы в директории с бэкапом
if [ ! -f "enabled_services.txt" ]; then
    echo "Ошибка: Запустите скрипт из директории с бэкапом!"
    echo "Обычно: $HOME/.pipewire_backup"
    exit 1
fi

# Восстанавливаем D-Bus файлы
echo "1. Восстановление D-Bus активации..."
for file in *.service.disabled; do
    if [ -f "$file" ]; then
        original="${file%.disabled}"
        sudo cp "$file" "/usr/share/dbus-1/services/$original" 2>/dev/null && \
        echo "  ✓ $original"
    fi
done

# Восстанавливаем .desktop файлы
echo "2. Восстановление автозапуска..."
for file in *.desktop.disabled; do
    if [ -f "$file" ]; then
        original="${file%.disabled}"
        if [[ "$file" == *"/etc/"* ]]; then
            sudo cp "$file" "/etc/xdg/autostart/$original" 2>/dev/null
        else
            cp "$file" "$HOME/.config/autostart/$original" 2>/dev/null
        fi
        echo "  ✓ $original"
    fi
done

# Размаскируем сервисы
echo "3. Размаскирование сервисов..."
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    systemctl --user unmask "$service" 2>/dev/null
    echo "  ✓ $service размаскирован"
done

# Включаем сервисы, которые были включены
echo "4. Включение сервисов..."
while IFS= read -r service; do
    if [[ "$service" == "ENABLED_SERVICES:" ]] || [[ -z "$service" ]]; then
        continue
    fi
    systemctl --user enable "$service" 2>/dev/null && \
    echo "  ✓ Включен: $service"
done < enabled_services.txt

# Перезагружаем демон
systemctl --user daemon-reload

echo ""
echo "Восстановление завершено!"
echo "Для запуска PipeWire выполните:"
echo "  systemctl --user start pipewire pipewire-pulse wireplumber"
echo "Или перезагрузитесь: sudo reboot"
EOF

chmod +x "$BACKUP_DIR/restore_pipewire.sh"

echo "========================================"
echo "  ОТКЛЮЧЕНИЕ ЗАВЕРШЕНО!"
echo "========================================"
echo ""
echo "Сделано:"
echo "1. ✓ Остановлены все процессы PipeWire"
echo "2. ✓ Отключен автозапуск через systemd"
echo "3. ✓ Заблокирована D-Bus активация"
echo "4. ✓ Заблокирован XDG autostart"
echo "5. ✓ Создан бэкап в: $BACKUP_DIR"
echo ""
echo "Для восстановления PipeWire выполните:"
echo "  cd $BACKUP_DIR && ./restore_pipewire.sh"
echo ""
echo "Для проверки свободных камер:"
echo "  sudo lsof /dev/video* 2>/dev/null || echo 'Камеры свободны'"
echo ""
echo "Рекомендуется перезагрузить систему:"
echo "  sudo reboot"


# ./07_disable_pipwire.sh 
# ========================================
#     ПОЛНОЕ ОТКЛЮЧЕНИЕ PIPEWIRE
# ========================================
# Бэкап конфигурации в: /home/pi/.pipewire_backup

# [1/7] Сохранение текущего состояния...

# [2/7] Бэкап конфигурационных файлов...
#   ✓ /usr/lib/systemd/user/pipewire.service
#   ✓ /usr/lib/systemd/user/pipewire-pulse.service
#   ✓ /usr/lib/systemd/user/wireplumber.service
#   ✓ /usr/lib/systemd/user/pipewire.socket
#   ✓ /usr/lib/systemd/user/pipewire-pulse.socket

# [3/7] Остановка процессов...
# ./07_disable_pipwire.sh: line 78: 16591 Killed                  
# sudo pkill -9 -f pipewire 2> /dev/null
# ./07_disable_pipwire.sh: line 79: 16595 Killed                  
# sudo pkill -9 -f wireplumber 2> /dev/null
# ./07_disable_pipwire.sh: line 80: 16599 Killed                  
# sudo pkill -9 -f pipewire-pulse 2> /dev/null
# [4/7] Отключение автозапуска...
# [5/7] Блокировка D-Bus активации...
# [6/7] Блокировка XDG autostart...
# [7/7] Проверка результата...
# -- Текущие процессы PipeWire: ---
# ✓ Все процессы PipeWire остановлены
# --- Статус сервисов: ---
# pipewire: статус=inactive
# inactive, автозапуск=masked
# disabled
# pipewire-pulse: статус=inactive
# inactive, автозапуск=masked
# disabled
# wireplumber: статус=inactive
# inactive, автозапуск=masked
# disabled
# pipewire.socket: статус=inactive
# inactive, автозапуск=masked
# disabled
# pipewire-pulse.socket: статус=inactive
# inactive, автозапуск=masked
# disabled

# --- Доступ к камерам: ---
# ✓ Камеры свободны
# ========================================
# ОТКЛЮЧЕНИЕ ЗАВЕРШЕНО!
# ========================================
# Сделано:
# 1. ✓ Остановлены все процессы PipeWire
# 2. ✓ Отключен автозапуск через systemd
# 3. ✓ Заблокирована D-Bus активация
# 4. ✓ Заблокирован XDG autostart
# 5. ✓ Создан бэкап в: /home/pi/.pipewire_backup

# Для восстановления PipeWire выполните:
# cd /home/pi/.pipewire_backup && ./restore_pipewire.sh

# Для проверки свободных камер:
# sudo lsof /dev/video* 2>/dev/null || echo 'Камеры свободны'

# Рекомендуется перезагрузить систему:
# sudo reboot