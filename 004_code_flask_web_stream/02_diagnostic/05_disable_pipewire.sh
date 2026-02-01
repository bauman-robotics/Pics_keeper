#!/bin/bash
# disable_pipewire.sh

echo "Stopping PipeWire services..."

# Способ 1: Принудительное завершение
sudo pkill -9 pipewire
sudo pkill -9 wireplumber
sudo pkill -9 pulseaudio

# Способ 2: Отключить автозагрузку (если установлен как system service)
if systemctl list-unit-files | grep -q pipewire; then
    echo "Disabling system-level PipeWire..."
    sudo systemctl disable --now pipewire pipewire-pulse wireplumber 2>/dev/null
fi

# Способ 3: Отключить user services
if [ -f "/home/pi/.config/systemd/user/pipewire.service" ]; then
    echo "Disabling user-level PipeWire..."
    sudo -u pi systemctl --user disable --now pipewire pipewire-pulse wireplumber 2>/dev/null
fi

# Способ 4: Удалить или переименовать конфиги (опционально)
sudo mv /etc/xdg/autostart/pipewire.desktop /etc/xdg/autostart/pipewire.desktop.disabled 2>/dev/null
sudo mv /etc/xdg/autostart/wireplumber.desktop /etc/xdg/autostart/wireplumber.desktop.disabled 2>/dev/null

echo "Checking for remaining processes..."
ps aux | grep -E '(pipewire|wireplumber|pulse)' | grep -v grep

echo "Done! Cameras should be free now."
