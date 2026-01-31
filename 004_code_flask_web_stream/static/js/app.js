// Конфигурация
const CONFIG = {
    maxAttempts: 5,
    statusUpdateInterval: 2000,
    cameraStatusUpdateInterval: 3000
};

// Глобальные переменные
let streamActive = false;
let frameCount = 0;
let connectionAttempts = 0;
let selectedCamera = null;
let camerasData = null;
let videoInitialized = false; // ← ДОБАВЬТЕ эту строку

// DOM элементы
const videoImg = document.getElementById('video-stream');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const streamStatus = document.getElementById('stream-status');
const frameCountDisplay = document.getElementById('frame-count');
const connectionStatus = document.getElementById('connection-status');
const currentCameraElem = document.getElementById('current-camera');
const cameraReadyStatusElem = document.getElementById('camera-ready-status');

// Инициализация
// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    updateUI();
    loadCameras();
    updateCameraStatus();
    
    // Инициализируем видео
    if (videoImg && !videoInitialized) {
        videoInitialized = true;
        
        // Устанавливаем начальный src ТОЛЬКО если стрим активен
        const urlParams = new URLSearchParams(window.location.search);
        const autoStart = urlParams.get('autostart');
        
        if (autoStart === 'true') {
            startStream();
        }
    }
    
    // Периодическое обновление статуса
    setInterval(updateStatus, CONFIG.statusUpdateInterval);
    setInterval(updateCameraStatus, CONFIG.cameraStatusUpdateInterval);
    
    // Закрытие модального окна по клику вне контента
    window.onclick = function(event) {
        const modal = document.getElementById('camera-modal');
        if (event.target === modal) {
            closeCameras();
        }
    };
});

// Основные функции
function updateUI() {
    if (streamActive) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        streamStatus.innerHTML = '<span class="status-indicator active"></span><strong>Активен</strong>';
        videoImg.style.display = 'block';
        
        // Включаем видео ТОЛЬКО если оно выключено
        if (!videoImg.src || !videoImg.src.includes('video_feed')) {
            videoImg.src = '/video_feed?' + Date.now();
        }
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        streamStatus.innerHTML = '<span class="status-indicator inactive"></span><strong>Остановлен</strong>';
        videoImg.style.display = 'none';
        connectionStatus.textContent = 'Не подключено';
        
        // Выключаем видео
        videoImg.src = '';
    }
}

// API функции
async function startStream() {
    console.log('Запуск стрима...');
    
    try {
        // Проверяем камеру перед запуском
        const cameraStatus = await fetch('/api/stream/status').then(r => r.json());
        if (!cameraStatus.camera_ready) {
            alert('⚠️ Камера не готова! Проверьте подключение камеры.');
            return;
        }
        
        const response = await fetch('/api/stream/start', { method: 'POST' });
        const result = await response.json();
        
        if (result.status === 'started' || result.status === 'already_running') {
            streamActive = true;
            frameCount = 0;
            connectionAttempts = 0;
            updateUI();
            
            // УБЕРИТЕ эту строку - видео уже загружено в HTML
            // videoImg.src = '/video_feed?' + Date.now(); // ← УДАЛИТЬ
            
            connectionStatus.textContent = 'Подключение...';
            console.log('Стрим успешно запущен');
            
            // Запускаем проверку подключения
            setTimeout(() => {
                checkStreamConnection();
            }, 1000);
        } else {
            alert('Ошибка запуска стрима: ' + result.message);
        }
    } catch (error) {
        console.error('Ошибка API:', error);
        alert('Ошибка связи с сервером');
    }
}

async function stopStream() {
    console.log('Остановка стрима...');
    
    try {
        const response = await fetch('/api/stream/stop', { method: 'POST' });
        const result = await response.json();
        
        if (result.status === 'stopped' || result.status === 'already_stopped') {
            streamActive = false;
            updateUI();
            videoImg.src = '';
            connectionStatus.textContent = 'Остановлено';
            console.log('Стрим успешно остановлен');
        } else {
            alert('Ошибка остановки стрима: ' + result.message);
        }
    } catch (error) {
        console.error('Ошибка API:', error);
        alert('Ошибка связи с сервером');
    }
}

// Обработчики событий видео
videoImg.onload = function() {
    if (streamActive) {
        connectionStatus.textContent = 'Подключено';
        frameCount++;
        frameCountDisplay.textContent = frameCount;
        checkStreamConnection();
    }
};

videoImg.onerror = function() {
    if (streamActive) {
        connectionAttempts++;
        console.log('Ошибка загрузки видео, попытка:', connectionAttempts);
        
        // Если ошибка, просто показываем статус
        connectionStatus.textContent = '❌ Ошибка подключения';
        
        // УБЕРИТЕ авто-переподключение
        // if (connectionAttempts < CONFIG.maxAttempts) {
        //     connectionStatus.textContent = '🔄 Переподключение...';
        //     setTimeout(() => {
        //         videoImg.src = '/video_feed?' + Date.now(); // УДАЛИТЬ
        //     }, 1000);
        // } else {
        //     connectionStatus.textContent = '❌ Ошибка подключения';
        //     alert('Не удалось подключиться к видео потоку. Проверьте сервер и камеру.');
        //     stopStream();
        // }
    }
};
// Функции для камер
async function checkCamera() {
    try {
        const response = await fetch('/api/camera/test');
        const result = await response.json();
        
        if (result.status === 'success') {
            alert(`✅ Камера работает!\nРазрешение: ${result.resolution}\nFPS: ${result.fps}`);
            return true;
        } else {
            alert(`❌ Проблема с камерой:\n${result.message}`);
            return false;
        }
    } catch (error) {
        console.error('Ошибка проверки камеры:', error);
        alert('❌ Ошибка проверки камеры');
        return false;
    }
}

function checkStreamConnection() {
    if (!streamActive) return;
    
    if (videoImg.complete && videoImg.naturalWidth > 0) {
        connectionStatus.textContent = '✅ Подключено';
        connectionAttempts = 0;
    } else {
        // Просто показываем статус, не переподключаем автоматически
        connectionStatus.textContent = '🔄 Подключение...';
    }
}
function refreshStream() {
    if (streamActive) {
        console.log('Обновление видеопотока...');
        // Меняем src для принудительного обновления
        videoImg.src = '/video_feed?' + Date.now();
        connectionStatus.textContent = '🔄 Обновление...';
    } else {
        alert('Сначала запустите стрим!');
    }
}

async function restartStream() {
    if (streamActive) {
        await stopStream();
        setTimeout(async () => {
            await startStream();
        }, 1000);
    } else {
        await startStream();
    }
}

// Функции для работы с камерами
async function loadCameras() {
    const cameraList = document.getElementById('camera-list');
    cameraList.innerHTML = '<div class="loading">Загрузка списка камер...</div>';
    
    try {
        const response = await fetch('/api/cameras');
        const data = await response.json();
        renderMainCamerasList(data);
    } catch (error) {
        console.error('Ошибка загрузки камер:', error);
        cameraList.innerHTML = '<div class="error">Ошибка загрузки списка камер</div>';
    }
}

function renderMainCamerasList(data) {
    const cameraList = document.getElementById('camera-list');
    
    if (!data.cameras || data.cameras.length === 0) {
        cameraList.innerHTML = '<div class="error">Камеры не найдены</div>';
        return;
    }
    
    let html = '';
    
    data.cameras.forEach(camera => {
        let formatsStr = camera.formats ? camera.formats.join(', ') : 'Нет форматов';
        if (formatsStr.length > 50) {
            formatsStr = formatsStr.substring(0, 47) + '...';
        }
        
        let resolutionsHtml = '';
        if (camera.resolutions) {
            camera.resolutions.slice(0, 5).forEach(res => {
                resolutionsHtml += `<span class="resolution-tag-main">${res}</span>`;
            });
            if (camera.resolutions.length > 5) {
                resolutionsHtml += `<span class="resolution-tag-main">...</span>`;
            }
        }
        
        html += `
            <div class="camera-item-row ${camera.is_current ? 'current' : ''}">
                <input type="radio" name="camera" class="camera-radio" 
                       value="${camera.device_path}" ${camera.is_current ? 'checked' : ''} 
                       onchange="selectMainCamera('${camera.device_path}')">
                <div class="camera-info">
                    <div class="camera-name-main">${camera.name || camera.device_path}</div>
                    <div class="camera-details">
                        <span class="camera-device-main">${camera.device_path}</span>
                        <span class="camera-formats-main">Форматы: ${formatsStr}</span>
                    </div>
                    <div class="camera-resolutions-main">
                        Разрешения: ${resolutionsHtml}
                    </div>
                </div>
                <div class="camera-actions-main">
                    <button class="btn-apply ${camera.is_current ? '' : 'active'}" 
                            onclick="applyCamera('${camera.device_path}')"
                            ${camera.is_current ? 'disabled' : ''}>
                        Применить
                    </button>
                    ${camera.is_current ? '<span class="camera-status">Текущая камера</span>' : ''}
                </div>
            </div>
        `;
    });
    
    cameraList.innerHTML = html;
}

async function showCameras() {
    const modal = document.getElementById('camera-modal');
    const content = document.getElementById('camera-modal-content');
    
    modal.style.display = 'block';
    content.innerHTML = '<div class="loading">Загрузка списка камер...</div>';
    
    try {
        const response = await fetch('/api/cameras');
        const data = await response.json();
        camerasData = data;
        renderCamerasList(data);
    } catch (error) {
        console.error('Ошибка загрузки камер:', error);
        content.innerHTML = '<div class="error">Ошибка загрузки списка камер</div>';
    }
}

function closeCameras() {
    document.getElementById('camera-modal').style.display = 'none';
    selectedCamera = null;
    document.getElementById('select-camera-btn').disabled = true;
}

function renderCamerasList(data) {
    const content = document.getElementById('camera-modal-content');
    
    if (!data.cameras || data.cameras.length === 0) {
        content.innerHTML = '<div class="error">Камеры не найдены</div>';
        return;
    }
    
    let html = '<div class="camera-list">';
    
    data.cameras.forEach(camera => {
        const isSelected = selectedCamera === camera.device_path;
        const isCurrent = camera.is_current;
        
        let formatsStr = camera.formats ? camera.formats.join(', ') : 'Нет форматов';
        if (formatsStr.length > 50) {
            formatsStr = formatsStr.substring(0, 47) + '...';
        }
        
        let resolutionsHtml = '';
        if (camera.resolutions) {
            camera.resolutions.forEach(res => {
                resolutionsHtml += `<span class="resolution-tag">${res}</span>`;
            });
        }
        
        html += `
            <div class="camera-item ${isSelected ? 'selected' : ''} ${isCurrent ? 'current' : ''}" 
                 onclick="selectCameraItem('${camera.device_path}')">
                <div class="camera-header">
                    <div class="camera-name">${camera.name || camera.device_path}</div>
                    <div class="camera-device">${camera.device_path}</div>
                </div>
                <div class="camera-formats">Форматы: ${formatsStr}</div>
                <div class="camera-resolutions">
                    Разрешения: ${resolutionsHtml}
                </div>
                ${isCurrent ? '<div style="color: #007bff; font-size: 0.9em; margin-top: 5px;">Текущая камера</div>' : ''}
            </div>
        `;
    });
    
    html += '</div>';
    content.innerHTML = html;
}

function selectCameraItem(devicePath) {
    selectedCamera = devicePath;
    
    const items = document.querySelectorAll('.camera-item');
    items.forEach(item => {
        if (item.onclick.toString().includes(devicePath)) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
    
    document.getElementById('select-camera-btn').disabled = false;
}

async function selectCamera() {
    if (!selectedCamera) {
        alert('Пожалуйста, выберите камеру');
        return;
    }
    
    const btn = document.getElementById('select-camera-btn');
    btn.disabled = true;
    btn.textContent = 'Изменение камеры...';
    
    try {
        const response = await fetch('/api/cameras/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_path: selectedCamera })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            alert('Камера успешно изменена на ' + result.device_path);
            closeCameras();
            updateUI();
            
            if (streamActive) {
                stopStream();
                setTimeout(() => { startStream(); }, 1000);
            }
        } else {
            alert('Ошибка изменения камеры: ' + result.message);
            btn.disabled = false;
            btn.textContent = 'Выбрать камеру';
        }
    } catch (error) {
        console.error('Ошибка API:', error);
        alert('Ошибка связи с сервером');
        btn.disabled = false;
        btn.textContent = 'Выбрать камеру';
    }
}

function selectMainCamera(devicePath) {
    const items = document.querySelectorAll('.camera-item-row');
    items.forEach(item => {
        if (item.querySelector('.camera-radio').value === devicePath) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

async function applyCamera(devicePath) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Изменение...';
    
    try {
        const response = await fetch('/api/cameras/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_path: devicePath })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            alert('Камера успешно изменена на ' + result.device_path);
            loadCameras();
            
            if (streamActive) {
                stopStream();
                setTimeout(() => { startStream(); }, 1000);
            }
        } else {
            alert('Ошибка изменения камеры: ' + result.message);
            btn.disabled = false;
            btn.textContent = 'Применить';
        }
    } catch (error) {
        console.error('Ошибка API:', error);
        alert('Ошибка связи с сервером');
        btn.disabled = false;
        btn.textContent = 'Применить';
    }
}

// Вспомогательные функции
async function updateStatus() {
    try {
        const response = await fetch('/api/stream/status');
        const status = await response.json();
        
        frameCountDisplay.textContent = status.frame_count;
        
        if (!status.stream_active && streamActive) {
            streamActive = false;
            updateUI();
        }
    } catch (error) {
        console.error('Ошибка получения статуса:', error);
    }
}

async function updateCameraStatus() {
    try {
        const response = await fetch('/api/stream/status');
        const status = await response.json();
        
        currentCameraElem.textContent = status.camera_device || 'Неизвестно';
        
        const indicator = cameraReadyStatusElem.querySelector('.status-indicator');
        const text = cameraReadyStatusElem.querySelector('strong');
        
        if (status.camera_ready) {
            indicator.className = 'status-indicator active';
            text.textContent = '✅ Готова';
        } else {
            indicator.className = 'status-indicator inactive';
            text.textContent = '❌ Не готова';
        }
        
    } catch (error) {
        console.error('Ошибка обновления статуса камеры:', error);
    }
}
