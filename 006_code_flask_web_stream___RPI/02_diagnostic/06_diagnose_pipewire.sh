#!/bin/bash
# diagnose_pipewire.sh - Диагностика автозапуска PipeWire

echo "========================================="
echo "    DIAGNOSTICS: HOW PIPEWIRE STARTS     "
echo "========================================="
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Host: $(hostname)"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для проверки
check_item() {
    local description="$1"
    local command="$2"
    local file="$3"
    
    echo -e "\n${BLUE}=== $description ===${NC}"
    
    if [ -n "$file" ]; then
        if [ -e "$file" ]; then
            echo -e "${GREEN}✓ Файл существует:${NC} $file"
            echo "Содержимое (первые 10 строк):"
            echo "----------------------------------------"
            head -n 10 "$file" 2>/dev/null || echo "Не удалось прочитать"
            echo "----------------------------------------"
            
            # Проверка на скрытость (Hidden=true)
            if grep -q "Hidden=true" "$file" 2>/dev/null; then
                echo -e "${YELLOW}⚠ ВНИМАНИЕ: Файл скрыт (Hidden=true)${NC}"
            fi
        else
            echo -e "${RED}✗ Файл отсутствует:${NC} $file"
        fi
    fi
    
    if [ -n "$command" ]; then
        echo -e "\nВывод команды '$command':"
        echo "----------------------------------------"
        eval $command 2>/dev/null || echo "Команда не выполнена"
        echo "----------------------------------------"
    fi
}

# Создаем временный файл для сбора информации
TEMP_FILE="/tmp/pipewire_diagnostic_$(date +%s).txt"
exec > >(tee -a "$TEMP_FILE") 2>&1

# ============ 1. ТЕКУЩИЕ ПРОЦЕССЫ ============
check_item "1. ТЕКУЩИЕ ПРОЦЕССЫ PIPE/WIRE" "ps aux | grep -E '(pipewire|wireplumber|pulse)' | grep -v grep"

# ============ 2. SYSTEMD SERVICES ============
check_item "2. SYSTEMD USER SERVICES (уровень пользователя)" \
    "systemctl --user list-unit-files --all | grep -E '(pipewire|wireplumber|pulse)'" \
    "/home/$(whoami)/.config/systemd/user/pipewire.service"

check_item "3. SYSTEMD SYSTEM SERVICES (системный уровень)" \
    "sudo systemctl list-unit-files --all | grep -E '(pipewire|wireplumber|pulse)'" \
    "/lib/systemd/system/pipewire.service"

echo -e "\n${BLUE}Подробный статус сервисов:${NC}"
for service in pipewire pipewire-pulse wireplumber pipewire.socket; do
    echo -e "\nСервис: $service"
    echo "User level status:"
    systemctl --user status $service 2>&1 | head -20
    echo "System level status:"
    sudo systemctl status $service 2>&1 | head -20
done

# ============ 3. XDG AUTOSTART ============
check_item "4. XDG AUTOSTART FILES (глобальные)" "" \
    "/etc/xdg/autostart/pipewire.desktop"

check_item "5. XDG AUTOSTART FILES (пользовательские)" "" \
    "/home/$(whoami)/.config/autostart/pipewire.desktop"

echo -e "\n${BLUE}Все файлы .desktop связанные с PipeWire:${NC}"
find /etc/xdg/autostart /usr/share/autostart /home/$(whoami)/.config/autostart \
    -name "*pipewire*" -o -name "*wireplumber*" -o -name "*pulse*" 2>/dev/null | while read file; do
    echo -e "${GREEN}Найден:${NC} $file"
    echo "  Размер: $(ls -lh "$file" | awk '{print $5}')"
    echo "  Hidden: $(grep -i "hidden" "$file" 2>/dev/null || echo "не указано")"
done

# ============ 4. D-BUS АКТИВАЦИИ ============
check_item "6. D-BUS SERVICE FILES" "" \
    "/usr/share/dbus-1/services/org.freedesktop.PipeWire.service"

echo -e "\n${BLUE}Все D-Bus сервисы PipeWire:${NC}"
find /usr/share/dbus-1/services -name "*pipewire*" -o -name "*wireplumber*" 2>/dev/null | while read file; do
    echo -e "${GREEN}Найден:${NC} $file"
    echo "  Исполняемый файл: $(grep "^Exec=" "$file" 2>/dev/null || echo "не указан")"
done

# ============ 5. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ============
check_item "7. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ" \
    "env | grep -iE '(pipe|wire|pulse|audio)'" \
    ""

echo -e "\n${BLUE}Файлы окружения:${NC}"
for file in /etc/environment /etc/profile /home/$(whoami)/.profile /home/$(whoami)/.bashrc; do
    if [ -f "$file" ]; then
        echo -e "\nПроверка $file:"
        grep -iE "(PIPEWIRE|WIREPLUMBER|PULSE|AUDIO)" "$file" 2>/dev/null || echo "  Нет настроек PipeWire"
    fi
done

# ============ 6. PAM МОДУЛИ ============
check_item "8. PAM MODULES" \
    "grep -r "pipewire" /etc/pam.d/ 2>/dev/null || true" \
    ""

# ============ 7. ДЕМОНЫ И СКРИПТЫ ============
check_item "9. INIT SCRIPTS (SysV/init.d)" \
    "ls -la /etc/init.d/*pipe* /etc/init.d/*wire* 2>/dev/null || echo 'Нет init скриптов'" \
    ""

echo -e "\n${BLUE}Скрипты в rc.d:${NC}"
find /etc/rc*.d -name "*pipewire*" -o -name "*wireplumber*" 2>/dev/null | while read file; do
    echo -e "${YELLOW}Найден:${NC} $file -> $(readlink -f "$file" 2>/dev/null || echo 'не ссылка')"
done

# ============ 8. CRONTAB ============
check_item "10. CRONTAB ENTRIES" \
    "(crontab -l 2>/dev/null; sudo crontab -l 2>/dev/null) | grep -i pipewire || echo 'Нет записей в crontab'" \
    ""

# ============ 9. ПРОВЕРКА СЕССИИ ============
check_item "11. DESKTOP SESSION INFO" \
    "echo \"DESKTOP_SESSION: \$DESKTOP_SESSION\nXDG_CURRENT_DESKTOP: \$XDG_CURRENT_DESKTOP\nXDG_SESSION_TYPE: \$XDG_SESSION_TYPE\"" \
    ""

echo -e "\n${BLUE}Конфигурация сессии:${NC}"
SESSION_FILE="/home/$(whoami)/.xsessionrc"
if [ -f "$SESSION_FILE" ]; then
    grep -i "pipewire" "$SESSION_FILE" 2>/dev/null || echo "  Нет упоминаний PipeWire"
else
    echo "  Файл $SESSION_FILE не существует"
fi

# ============ 10. ПРОВЕРКА МОДУЛЕЙ ============
check_item "12. ЗАГРУЖЕННЫЕ МОДУЛИ ЯДРА" \
    "lsmod | grep -iE '(audio|snd|alsa)'" \
    ""

# ============ 11. СОХРАНЕНИЕ ИСТОРИИ ============
check_item "13. BACKUP ТЕКУЩЕЙ КОНФИГУРАЦИИ" \
    "echo 'Создание бэкапа конфигурации...'" \
    ""

BACKUP_DIR="/tmp/pipewire_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo -e "\n${GREEN}Создание бэкапов в:${NC} $BACKUP_DIR"
echo "Копирование конфигурационных файлов..."

# Копируем важные файлы
FILES_TO_BACKUP=(
    "/etc/xdg/autostart/pipewire.desktop"
    "/etc/xdg/autostart/wireplumber.desktop"
    "/home/$(whoami)/.config/autostart/pipewire.desktop"
    "/home/$(whoami)/.config/systemd/user/pipewire.service"
    "/lib/systemd/system/pipewire.service"
    "/usr/share/dbus-1/services/org.freedesktop.PipeWire.service"
    "/etc/environment"
    "/home/$(whoami)/.profile"
)

for file in "${FILES_TO_BACKUP[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/" 2>/dev/null && \
        echo "  ✓ Скопирован: $file" || \
        echo "  ✗ Ошибка копирования: $file"
    fi
done

# Сохраняем вывод systemd
systemctl --user list-unit-files --all | grep -E "(pipewire|wireplumber)" > "$BACKUP_DIR/systemd_user_services.txt"
sudo systemctl list-unit-files --all | grep -E "(pipewire|wireplumber)" > "$BACKUP_DIR/systemd_system_services.txt"

echo -e "\n${GREEN}Бэкап завершен. Файлы в:${NC} $BACKUP_DIR"
echo -e "${YELLOW}Для восстановления выполните:${NC}"
echo "  sudo cp $BACKUP_DIR/* /  # для системных файлов"
echo "  cp $BACKUP_DIR/* ~/      # для пользовательских файлов"

# ============ 12. ГЕНЕРАЦИЯ ОТЧЕТА ============
echo -e "\n${BLUE}=========================================${NC}"
echo -e "${GREEN}ДИАГНОСТИКА ЗАВЕРШЕНА${NC}"
echo -e "${BLUE}=========================================${NC}"

echo -e "\n${YELLOW}РЕКОМЕНДАЦИИ:${NC}"
echo "1. Проверьте раздел 'ТЕКУЩИЕ ПРОЦЕССЫ' - кто запустил PipeWire"
echo "2. Проверьте 'SYSTEMD SERVICES' - какие сервисы включены"
echo "3. Проверьте 'XDG AUTOSTART' - автозапуск из рабочего стола"
echo "4. Проверьте 'D-BUS АКТИВАЦИИ' - запуск по требованию"
echo "5. Полный отчет сохранен в: $TEMP_FILE"
echo "6. Бэкап конфигурации в: $BACKUP_DIR"

echo -e "\n${YELLOW}СКРИПТ ДЛЯ ВОССТАНОВЛЕНИЯ (restore_pipewire.sh):${NC}"
cat > "$BACKUP_DIR/restore_pipewire.sh" << 'EOF'
#!/bin/bash
# Скрипт восстановления PipeWire

echo "Восстановление PipeWire автозапуска..."

# Восстанавливаем systemd сервисы
if [ -f "systemd_user_services.txt" ]; then
    echo "Восстановление user services..."
    while read line; do
        service=$(echo $line | awk '{print $1}')
        status=$(echo $line | awk '{print $2}')
        if [ "$status" = "enabled" ]; then
            systemctl --user enable $service 2>/dev/null
        fi
    done < systemd_user_services.txt
fi

# Восстанавливаем файлы
for file in *; do
    if [ "$file" != "systemd_user_services.txt" ] && [ "$file" != "systemd_system_services.txt" ]; then
        if [[ "$file" == *".desktop" ]] || [[ "$file" == *".service" ]]; then
            if [[ "$file" == *"pipewire"* ]] || [[ "$file" == *"wireplumber"* ]]; then
                # Определяем куда копировать
                if [[ "$file" == *"/etc/"* ]]; then
                    dest="/etc/${file#*/etc/}"
                    sudo cp "$file" "$dest" && echo "Восстановлен: $dest"
                elif [[ "$file" == *"/home/"* ]]; then
                    dest="$HOME/${file#*/home/*/}"
                    cp "$file" "$dest" && echo "Восстановлен: $dest"
                else
                    dest="/usr/share/dbus-1/services/${file##*/}"
                    sudo cp "$file" "$dest" && echo "Восстановлен: $dest"
                fi
            fi
        fi
    fi
done

echo "Готово! Перезагрузите систему: sudo reboot"
EOF

chmod +x "$BACKUP_DIR/restore_pipewire.sh"
echo -e "\nФайл для восстановления создан: $BACKUP_DIR/restore_pipewire.sh"

echo -e "\n${YELLOW}БЫСТРАЯ КОМАНДА ДЛЯ ВКЛЮЧЕНИЯ PIPE/WIRE:${NC}"
echo "  systemctl --user enable --now pipewire pipewire-pulse wireplumber"
echo "  sudo systemctl enable --now pipewire pipewire-pulse wireplumber"

echo -e "\n${GREEN}Полный отчет:${NC} $TEMP_FILE"
echo -e "${GREEN}Бэкап файлов:${NC} $BACKUP_DIR"
echo ""
echo "Для принудительного запуска PipeWire:"
echo "  pipewire &"
echo "  wireplumber &"
echo "  pipewire-pulse &"