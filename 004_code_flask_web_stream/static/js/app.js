class StreamController {
    constructor() {
        this.isStreamActive = false;
        this.statusInterval = null;
        this.videoElement = document.getElementById('video-stream');
        this.currentDevicePath = null;
        this.init();
    }
    
    async init() {
        await this.loadCameras();
        await this.checkStatus();
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
        if (typeof deviceId === 'number') {
            // Если это число (0, 1, 2...) - преобразуем в /dev/videoX
            this.currentDevicePath = `/dev/video${deviceId}`;
        } else if (deviceId && deviceId.startsWith('/dev/')) {
            this.currentDevicePath = deviceId;
        } else {
            // Пробуем получить из API статуса
            try {
                const response = await fetch('/api/stream/status');
                const status = await response.json();
                this.currentDevicePath = status.camera_device || '/dev/video0';
            } catch {
                this.currentDevicePath = '/dev/video0';
            }
        }
        console.log(`🎯 Текущее устройство: ${this.currentDevicePath}`);
    }
    
    renderCameraList(cameras) {
        const container = document.getElementById('camera-list');
        if (!container) return;
        
        container.innerHTML = cameras.map(camera => `
            <div class="camera-card ${camera.device_path === this.currentDevicePath ? 'current' : ''}" 
                 onclick="selectCamera('${camera.device_path}')"
                 title="Нажмите для выбора">
                <div class="camera-header">
                    <span class="camera-icon">📷</span>
                    <span class="camera-name">${this.escapeHtml(camera.name || camera.device_path)}</span>
                </div>
                <div class="camera-details">
                    <div class="camera-path">${camera.device_path}</div>
                    ${camera.device_path === this.currentDevicePath ? '<div class="current-badge">Текущая</div>' : ''}
                </div>
                <div class="camera-formats">
                    <small>Форматы: ${camera.formats?.join(', ') || 'неизвестно'}</small>
                </div>
            </div>
        `).join('');
    }
    
    updateCurrentCameraDisplay(cameras) {
        const currentCamera = cameras.find(cam => cam.device_path === this.currentDevicePath);
        const displayElement = document.getElementById('current-camera');
        
        if (displayElement) {
            if (currentCamera) {
                displayElement.textContent = `${currentCamera.name} (${currentCamera.device_path})`;
            } else {
                displayElement.textContent = `Устройство ${this.currentDevicePath}`;
            }
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
            //alert(`✅ Камера изменена на ${devicePath}`);
            streamController?.loadCameras();
            streamController?.checkStatus();
            
            // Если стрим был активен, перезапускаем его
            if (data.stream_active) {
                setTimeout(() => {
                    streamController?.refreshVideo();
                }, 500);
            }
        } else {
            console.error('❌ Ошибка выбора камеры:', data.message);
            alert('❌ Ошибка: ' + data.message);
        }
    } catch (error) {
        console.error('❌ Ошибка выбора камеры:', error);
        alert('❌ Ошибка выбора камеры: ' + error.message);
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