class StreamController {
    constructor() {
        this.isStreamActive = false;
        this.statusInterval = null;
        this.videoElement = document.getElementById('video-stream');
        this.currentDevicePath = null;

        // Сразу показываем базовую информацию
        this.updateInitialDisplay();

        this.init();
    }

    updateInitialDisplay() {
        // Показываем базовый статус
        const cameraStatus = document.getElementById('camera-ready-status');
        if (cameraStatus) {
            cameraStatus.innerHTML = '<span class="status-indicator ready"></span><strong>Проверка...</strong>';
        }
        
        // Показываем текущую камеру
        const currentCameraDisplay = document.getElementById('current-camera-display');
        if (currentCameraDisplay) {
            currentCameraDisplay.innerHTML = '<span style="color: #48bb78;">Загрузка...</span>';
        }
    }    
    
    async init() {
        // Сначала проверяем статус, чтобы получить текущее устройство с сервера
        await this.checkStatus();
        
        // Затем загружаем камеры (теперь currentDevicePath уже определен)
        await this.loadCameras();
        
        // Запускаем обновление статуса
        this.startStatusUpdates();
    }

    async loadCameras() {
        try {
            console.log('🔄 Загрузка списка камер...');
            const response = await fetch('/api/cameras');
            if (!response.ok) {
                throw new Error(`HTTP ошибка: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('📷 Получены камеры:', data);
            
            // Определяем текущее устройство
            await this.determineCurrentDevice(data.current_device);
            
            if (data.cameras && data.cameras.length > 0) {
                this.renderCameraList(data.cameras);
                this.updateCurrentCameraDisplay(data.cameras);
            } else {
                this.showNoCamerasMessage();
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки камер:', error);
            this.showErrorMessage('Ошибка загрузки камер: ' + error.message);
        }
    }
    
    async determineCurrentDevice(deviceId) {
        console.log('🔍 Определение устройства из:', deviceId, typeof deviceId);
        
        // Добавляем отладку
        if (deviceId === undefined || deviceId === null) {
            console.log('⚠️ deviceId не определен');
            this.currentDevicePath = '/dev/video0';
        } 
        else if (typeof deviceId === 'number') {
            this.currentDevicePath = `/dev/video${deviceId}`;
            console.log(`✅ Число ${deviceId} → ${this.currentDevicePath}`);
        } 
        else if (typeof deviceId === 'string') {
            // Пробуем разные форматы
            if (deviceId.startsWith('/dev/')) {
                this.currentDevicePath = deviceId;
                console.log(`✅ Путь ${deviceId} → ${this.currentDevicePath}`);
            } 
            else if (!isNaN(parseInt(deviceId))) {
                // Если строка содержит число
                this.currentDevicePath = `/dev/video${parseInt(deviceId)}`;
                console.log(`✅ Строка-число "${deviceId}" → ${this.currentDevicePath}`);
            }
            else {
                console.log(`⚠️ Неизвестный формат строки: "${deviceId}"`);
                this.currentDevicePath = '/dev/video0';
            }
        }
        else {
            console.log(`⚠️ Неизвестный тип: ${typeof deviceId}, значение: ${deviceId}`);
            this.currentDevicePath = '/dev/video0';
        }
        
        console.log(`🎯 Установлено текущее устройство: ${this.currentDevicePath}`);
    }
    
    renderCameraList(cameras) {
        const container = document.getElementById('camera-list');
        if (!container) return;
        
        if (!cameras || cameras.length === 0) {
            container.innerHTML = '<div class="no-cameras">Камеры не найдены</div>';
            return;
        }
        
        console.log('📋 Рендеринг списка камер:', {
            total: cameras.length,
            currentDevice: this.currentDevicePath,
            cameras: cameras.map(c => ({ path: c.device_path, name: c.name }))
        });
        
        container.innerHTML = cameras.map(camera => {
            let cameraName = camera.name || camera.device_path;
            cameraName = cameraName.replace(/\(usb-[^)]+\)/g, '').trim();
            cameraName = cameraName.replace(/\(046d:0825\)/g, '').trim();
            cameraName = cameraName.replace(/:/g, '').trim();
            
            if (cameraName.length > 25) {
                cameraName = cameraName.substring(0, 22) + '...';
            }
            
            const isSelected = camera.device_path === this.currentDevicePath;
            
            // Отладка для каждой камеры
            if (isSelected) {
                console.log(`✅ Найдена текущая камера: ${camera.device_path} (${cameraName})`);
            }
            
            return `
                <div class="camera-card ${isSelected ? 'selected' : ''}" 
                    onclick="handleCameraChange('${camera.device_path}')"
                    title="${camera.name || camera.device_path}">
                    <div class="camera-selector">
                        <div class="selection-square ${isSelected ? 'selected' : ''}">
                            ${isSelected ? '✓' : ''}
                        </div>
                        <div class="camera-info">
                            <div class="camera-header">
                                <span class="camera-name">${this.escapeHtml(cameraName)}</span>
                                ${isSelected ? '<span class="current-badge">Текущая</span>' : ''}
                            </div>
                            <div class="camera-path">${camera.device_path}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    updateCurrentCameraDisplay(cameras) {
        const currentCamera = cameras.find(cam => cam.device_path === this.currentDevicePath);
        const displayElement = document.getElementById('current-camera-display');
        
        if (displayElement && currentCamera) {
            let cameraName = currentCamera.name || currentCamera.device_path;
            cameraName = cameraName.replace(/\(usb-[^)]+\)/g, '').trim();
            cameraName = cameraName.replace(/\(046d:0825\)/g, '').trim();
            cameraName = cameraName.replace(/:/g, '').trim();
            
            if (cameraName.length > 20) {
                cameraName = cameraName.substring(0, 17) + '...';
            }
            
            displayElement.innerHTML = `
                <span style="color: #48bb78; font-weight: bold;">${cameraName}</span>
                <span style="color: #a0aec0; font-size: 0.9em; margin-left: 5px;">(${currentCamera.device_path})</span>
            `;
        }
    }
    
    showNoCamerasMessage() {
        const container = document.getElementById('camera-list');
        if (container) {
            container.innerHTML = `
                <div class="no-cameras-message">
                    <div class="message-icon">❌</div>
                    <div class="message-text">Камеры не найдены</div>
                    <div class="message-hint">
                        Проверьте подключение камеры и запустите:<br>
                        <code>ls /dev/video*</code><br>
                        <button class="btn btn-sm btn-secondary" onclick="refreshCameras()">
                            🔄 Обновить список
                        </button>
                    </div>
                </div>
            `;
        }
    }
    
    showErrorMessage(message) {
        const container = document.getElementById('camera-list');
        if (container) {
            container.innerHTML = `
                <div class="error-message">
                    <div class="message-icon">⚠️</div>
                    <div class="message-text">${message}</div>
                    <button class="btn btn-sm btn-secondary" onclick="refreshCameras()">
                        🔄 Попробовать снова
                    </button>
                </div>
            `;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    async startStream() {
        try {
            console.log('▶️ Запуск стрима...');
            const response = await fetch('/api/stream/start', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'started' || data.status === 'already_running') {
                this.updateUI(true);
                this.refreshVideo();
                console.log('✅ Стрим запущен');
            } else {
                console.error('❌ Ошибка запуска:', data.message);
                alert('Ошибка запуска стрима: ' + data.message);
            }
        } catch (error) {
            console.error('❌ Ошибка запуска стрима:', error);
            alert('Ошибка запуска стрима: ' + error.message);
        }
    }
    
    async stopStream() {
        try {
            console.log('⏹️ Остановка стрима...');
            const response = await fetch('/api/stream/stop', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'stopped' || data.status === 'already_stopped') {
                this.updateUI(false);
                console.log('✅ Стрим остановлен');
            } else {
                console.error('❌ Ошибка остановки:', data.message);
                alert('Ошибка остановки стрима: ' + data.message);
            }
        } catch (error) {
            console.error('❌ Ошибка остановки стрима:', error);
            alert('Ошибка остановки стрима: ' + error.message);
        }
    }
    
    async checkStatus() {
        try {
            const response = await fetch('/api/stream/status');
            const data = await response.json();
            this.updateUI(data.stream_active);
            this.updateStatusInfo(data);
            
            // Обновляем информацию о текущей камере
            if (data.camera_device && data.camera_device !== this.currentDevicePath) {
                this.currentDevicePath = data.camera_device;
                this.loadCameras(); // Перезагружаем список камер
            }
            
        } catch (error) {
            console.error('❌ Ошибка проверки статуса:', error);
        }
    }
    
    updateUI(isActive) {
        this.isStreamActive = isActive;
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const statusEl = document.getElementById('stream-status');
        
        if (startBtn) startBtn.disabled = isActive;
        if (stopBtn) stopBtn.disabled = !isActive;
        
        if (statusEl) {
            if (isActive) {
                statusEl.innerHTML = '<span class="status-indicator active"></span><strong>Активен</strong>';
            } else {
                statusEl.innerHTML = '<span class="status-indicator inactive"></span><strong>Остановлен</strong>';
            }
        }
    }
    
    updateStatusInfo(data) {
        const frameCountEl = document.getElementById('frame-count');
        const cameraStatusEl = document.getElementById('camera-ready-status');
        const connectionStatusEl = document.getElementById('connection-status');
        
        if (frameCountEl) {
            frameCountEl.textContent = data.frame_count || '0';
        }
        
        if (cameraStatusEl) {
            cameraStatusEl.innerHTML = data.camera_ready ? 
                '<span class="status-indicator active"></span><strong>Готова</strong>' :
                '<span class="status-indicator inactive"></span><strong>Не готова</strong>';
        }
        
        if (connectionStatusEl) {
            connectionStatusEl.textContent = data.stream_active ? 'Подключено' : 'Отключено';
        }
    }
    
    refreshVideo() {
        if (this.videoElement) {
            const src = this.videoElement.src;
            this.videoElement.src = '';
            setTimeout(() => {
                this.videoElement.src = src + '?t=' + Date.now();
                console.log('🔄 Видео обновлено');
            }, 100);
        }
    }
    
    startStatusUpdates() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
        this.statusInterval = setInterval(() => this.checkStatus(), 3000);
    }
    
    destroy() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }
}

// Глобальные функции
let streamController;

document.addEventListener('DOMContentLoaded', () => {
    streamController = new StreamController();
});

function startStream() { 
    streamController?.startStream(); 
}

function stopStream() { 
    streamController?.stopStream(); 
}

function refreshStream() { 
    streamController?.refreshVideo(); 
}

function refreshCameras() {
    streamController?.loadCameras();
}

function restartStream() {
    console.log('🔄 Перезапуск стрима...');
    stopStream();
    setTimeout(() => {
        startStream();
    }, 1000);
}

async function selectCamera(devicePath) {
    try {
        console.log(`🎯 Выбор камеры: ${devicePath}`);
        const response = await fetch('/api/cameras/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_path: devicePath })
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log(`✅ Камера изменена на ${devicePath}`);
            // БЕЗ ALERT: streamController?.loadCameras();
            // БЕЗ ALERT: streamController?.checkStatus();
            
            // Используем handleCameraChange для обновления интерфейса
            handleCameraChange(devicePath);
        } else {
            console.error('❌ Ошибка выбора камеры:', data.message);
            // Можно оставить alert для ошибок или убрать
            // alert('❌ Ошибка: ' + data.message);
        }
    } catch (error) {
        console.error('❌ Ошибка выбора камеры:', error);
        // alert('❌ Ошибка выбора камеры: ' + error.message);
    }
}

// Проверка камеры
async function checkCamera() {
    try {
        const response = await fetch('/api/camera/test');
        const data = await response.json();
        
        if (data.status === 'success') {
            alert(`✅ Камера работает\nРазрешение: ${data.resolution}\nFPS: ${data.fps}`);
        } else {
            alert(`❌ Камера не работает: ${data.message}`);
        }
    } catch (error) {
        alert('❌ Ошибка проверки камеры: ' + error.message);
    }
}

// Диагностика стрима
async function checkStreamDiagnostics() {
    try {
        const response = await fetch('/api/stream/diagnostics');
        const data = await response.json();
        console.log('🔧 Диагностика:', data);
        alert(JSON.stringify(data, null, 2));
    } catch (error) {
        alert('❌ Ошибка диагностики: ' + error.message);
    }
}

// Показать все камеры (открыть модальное окно)
function showAllCameras() {
    const modal = document.getElementById('camera-modal');
    if (modal) {
        modal.style.display = 'block';
        refreshCameras();
    }
}

// Обработка загрузки видео
function onVideoLoad() {
    console.log('✅ Видео загружено');
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'none';
    
    // Обновляем информацию о размере
    const video = document.getElementById('video-stream');
    if (video.naturalWidth > 0) {
        const info = `${video.naturalWidth}×${video.naturalHeight}`;
        const sizeElement = document.getElementById('stream-size');
        if (sizeElement) sizeElement.textContent = `Размер: ${info}`;
    }
}

function onVideoError() {
    console.log('❌ Ошибка загрузки видео');
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'flex';
}

// Очистка при закрытии страницы
window.addEventListener('beforeunload', () => {
    streamController?.destroy();
});