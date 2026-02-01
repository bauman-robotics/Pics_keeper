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
echo -e "\n[1/7] Сохранение текущего состояния..."

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
echo -e "\n[2/7] Бэкап конфигурационных файлов..."

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
echo -e "\n[3/7] Остановка процессов..."

# Останавливаем user сервисы
systemctl --user stop pipewire pipewire-pulse wireplumber 2>/dev/null
systemctl --user stop pipewire.socket pipewire-pulse.socket 2>/dev/null

# Принудительно убиваем процессы
sudo pkill -9 -f pipewire 2>/dev/null
sudo pkill -9 -f wireplumber 2>/dev/null
sudo pkill -9 -f pipewire-pulse 2>/dev/null

# ============ 3. ОТКЛЮЧЕНИЕ АВТОЗАПУСКА ============
echo -e "\n[4/7] Отключение автозапуска..."

# Отключаем и маскируем user сервисы
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    systemctl --user disable $service 2>/dev/null
    systemctl --user mask $service 2>/dev/null
done

# Отключаем system сервисы (если есть)
sudo systemctl disable pipewire pipewire-pulse wireplumber 2>/dev/null
sudo systemctl mask pipewire pipewire-pulse wireplumber 2>/dev/null

# ============ 4. БЛОКИРОВКА D-BUS АКТИВАЦИИ ============
echo -e "\n[5/7] Блокировка D-Bus активации..."

# Переименовываем D-Bus файлы
for dbus_file in /usr/share/dbus-1/services/*pipewire* /usr/share/dbus-1/services/*wireplumber*; do
    if [ -f "$dbus_file" ]; then
        sudo mv "$dbus_file" "${dbus_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $dbus_file"
    fi
done

# ============ 5. БЛОКИРОВКА XDG AUTOSTART ============
echo -e "\n[6/7] Блокировка XDG autostart..."

# Глобальные .desktop файлы
for desktop_file in /etc/xdg/autostart/*pipewire* /etc/xdg/autostart/*wireplumber*; do
    if [ -f "$desktop_file" ]; then
        sudo mv "$desktop_file" "${desktop_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $desktop_file"
    fi
done

# Пользовательские .desktop файлы
for desktop_file in $HOME/.config/autostart/*pipewire* $HOME/.config/autostart/*wireplumber*; do
    if [ -f "$desktop_file" ]; then
        mv "$desktop_file" "${desktop_file}.disabled" 2>/dev/null && \
        echo "  ✓ Заблокирован: $desktop_file"
    fi
done

# ============ 6. ПРОВЕРКА РЕЗУЛЬТАТА ============
echo -e "\n[7/7] Проверка результата..."

sleep 2

echo -e "\n--- Текущие процессы PipeWire: ---"
if pgrep -f "pipewire|wireplumber" >/dev/null; then
    echo "⚠ Некоторые процессы все еще активны:"
    ps aux | grep -E "(pipewire|wireplumber)" | grep -v grep
    echo "Принудительное завершение..."
    sudo pkill -KILL -f "pipewire|wireplumber"
else
    echo "✓ Все процессы PipeWire остановлены"
fi

echo -e "\n--- Статус сервисов: ---"
for service in pipewire pipewire-pulse wireplumber pipewire.socket pipewire-pulse.socket; do
    status=$(systemctl --user is-active $service 2>/dev/null || echo "inactive")
    enabled=$(systemctl --user is-enabled $service 2>/dev/null || echo "disabled")
    echo "  $service: статус=$status, автозапуск=$enabled"
done

echo -e "\n--- Доступ к камерам: ---"
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
    systemctl --user unmask $service 2>/dev/null
    echo "  ✓ $service размаскирован"
done

# Включаем сервисы, которые были включены
echo "4. Включение сервисов..."
while read -r service; do
    if [[ "$service" == "ENABLED_SERVICES:" ]] || [[ -z "$service" ]]; then
        continue
    fi
    systemctl --user enable $service 2>/dev/null && \
    echo "  ✓ Включен: $service"
done < enabled_services.txt

# Перезагружаем демон
systemctl --user daemon-reload

echo -e "\nВосстановление завершено!"
echo "Для запуска PipeWire выполните:"
echo "  systemctl --user start pipewire pipewire-pulse wireplumber"
echo "Или перезагрузитесь: sudo reboot"
EOF

chmod +x "$BACKUP_DIR/restore_pipewire.sh"

echo "========================================"
echo "  ОТКЛЮЧЕНИЕ ЗАВЕРШЕНО!"
echo "========================================"
echo -e "\nСделано:"
echo "1. ✓ Остановлены все процессы PipeWire"
echo "2. ✓ Отключен автозапуск через systemd"
echo "3. ✓ Заблокирована D-Bus активация"
echo "4. ✓ Заблокирован XDG autostart"
echo "5. ✓ Создан бэкап в: $BACKUP_DIR"
echo -e "\nДля восстановления PipeWire выполните:"
echo "  cd $BACKUP_DIR && ./restore_pipewire.sh"
echo -e "\nДля проверки свободных камер:"
echo "  sudo lsof /dev/video* 2>/dev/null || echo 'Камеры свободны'"
echo -e "\nРекомендуется перезагрузить систему:"
echo "  sudo reboot"