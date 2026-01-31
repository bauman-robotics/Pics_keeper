// ============================================
// app.js - Управление веб-камерой и видеопотоком
// Версия с автоматическим запуском и улучшенной обработкой ошибок
// ============================================

// Конфигурация
const CONFIG = {
    maxAttempts: 5,
    statusUpdateInterval: 2000,
    cameraStatusUpdateInterval: 3000,
    autoStartStream: true,  // Автоматически запускать стрим при загрузке
    videoFeedRetryDelay: 3000,  // Задержка переподключения видео
    serverCheckTimeout: 3000  // Таймаут проверки сервера
};

// Глобальные переменные
let streamActive = false;
let frameCount = 0;
let connectionAttempts = 0;
let selectedCamera = null;
let camerasData = null;
let camerasLoading = false;
let videoInitialized = false;

// DOM элементы
const videoImg = document.getElementById('video-stream');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const streamStatus = document.getElementById('stream-status');
const frameCountDisplay = document.getElementById('frame-count');
const connectionStatus = document.getElementById('connection-status');
const currentCameraElem = document.getElementById('current-camera');
const cameraReadyStatusElem = document.getElementById('camera-ready-status');
const cameraListElem = document.getElementById('camera-list');

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================

// Проверяем доступность сервера при загрузке
async function checkServerAvailability() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.serverCheckTimeout);
        
        const response = await fetch('/api/stream/status', { 
            signal: controller.signal 
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            console.log('✅ Сервер доступен');
            return true;
        }
    } catch (error) {
        console.log('❌ Сервер не отвечает:', error.name);
    }
    return false;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Инициализация приложения...');
    
    // Инициализируем UI
    updateUI();
    
    // Проверяем доступность сервера
    const serverAvailable = await checkServerAvailability();
    
    if (serverAvailable) {
        // Загружаем камеры
        loadCameras();
        updateCameraStatus();
        
        // Автоматически запускаем стрим если включено в конфиге
        if (CONFIG.autoStartStream) {
            console.log('⚡ Автоматический запуск стрима...');
            setTimeout(() => {
                if (!streamActive) {
                    startStream();
                }
            }, 1500);
        }
    } else {
        // Сервер не доступен
        connectionStatus.textContent = '❌ Сервер не доступен';
        console.error('Сервер не доступен, проверьте запущен ли сервер');
        
        // Показываем сообщение
        if (cameraListElem) {
            cameraListElem.innerHTML = '<div class="error">Сервер не доступен. Проверьте запущен ли сервер.</div>';
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
    
    console.log('✅ Приложение инициализировано');
});

// ============================================
// ОСНОВНЫЕ ФУНКЦИИ
// ============================================

function updateUI() {
    if (streamActive) {
        // Стрим активен
        startBtn.disabled = true;
        stopBtn.disabled = false;
        streamStatus.innerHTML = '<span class="status-indicator active"></span><strong>Активен</strong>';
        
        if (videoImg) {
            videoImg.style.display = 'block';
            // Включаем видео если оно выключено
            if (!videoImg.src || !videoImg.src.includes('video_feed')) {
                videoImg.src = '/video_feed?' + Date.now();
            }
        }
    } else {
        // Стрим остановлен
        startBtn.disabled = false;
        stopBtn.disabled = true;
        streamStatus.innerHTML = '<span class="status-indicator inactive"></span><strong>Остановлен</strong>';
        
        if (videoImg) {
            videoImg.style.display = 'none';
            connectionStatus.textContent = 'Не подключено';
        }
    }
}

// ============================================
// API ФУНКЦИИ - СТРИМ
// ============================================

async function startStream() {
    console.log('🟢 Запуск стрима...');
    
    try {
        // Проверяем камеру перед запуском
        const cameraStatus = await fetch('/api/stream/status').then(r => r.json());
        console.log('📊 Статус камеры:', cameraStatus);
        
        if (!cameraStatus.camera_ready) {
            console.warn('⚠️ Камера не готова!');
            alert('⚠️ Камера не готова! Проверьте подключение камеры.');
            return;
        }
        
        const response = await fetch('/api/stream/start', { method: 'POST' });
        const result = await response.json();
        console.log('📋 Результат запуска:', result);
        
        if (result.status === 'started' || result.status === 'already_running') {
            streamActive = true;
            frameCount = 0;
            connectionAttempts = 0;
            updateUI();
            
            connectionStatus.textContent = 'Подключение...';
            console.log('✅ Стрим успешно запущен');
            
            // Проверяем подключение через секунду
            setTimeout(() => {
                checkStreamConnection();
            }, 1000);
        } else {
            console.error('❌ Ошибка запуска стрима:', result.message);
            alert('Ошибка запуска стрима: ' + result.message);
        }
    } catch (error) {
        console.error('❌ Ошибка API:', error);
        alert('Ошибка связи с сервером');
    }
}

async function stopStream() {
    console.log('🔴 Остановка стрима...');
    
    try {
        const response = await fetch('/api/stream/stop', { method: 'POST' });
        const result = await response.json();
        
        if (result.status === 'stopped' || result.status === 'already_stopped') {
            streamActive = false;
            updateUI();
            connectionStatus.textContent = 'Остановлено';
            console.log('✅ Стрим успешно остановлен');
        } else {
            alert('Ошибка остановки стрима: ' + result.message);
        }
    } catch (error) {
        console.error('❌ Ошибка API:', error);
        alert('Ошибка связи с сервером');
    }
}

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ ВИДЕО
// ============================================

if (videoImg) {
    videoImg.onload = function() {
        console.log('📹 Видеопоток загружен');
        if (streamActive) {
            connectionStatus.textContent = '✅ Подключено';
            frameCount++;
            frameCountDisplay.textContent = frameCount;
        }
    };

    videoImg.onerror = function() {
        console.log('❌ Ошибка загрузки видеопотока');
        if (streamActive) {
            connectionAttempts++;
            console.log('Ошибка загрузки видео, попытка:', connectionAttempts);
            
            if (connectionAttempts < CONFIG.maxAttempts) {
                connectionStatus.textContent = '🔄 Переподключение...';
                setTimeout(() => {
                    videoImg.src = '/video_feed?' + Date.now();
                }, CONFIG.videoFeedRetryDelay);
            } else {
                connectionStatus.textContent = '❌ Ошибка подключения';
                alert('Не удалось подключиться к видео потоку. Проверьте сервер и камеру.');
                stopStream();
            }
        }
    };
}

// ============================================
// ФУНКЦИИ ДЛЯ РАБОТЫ С КАМЕРАМИ
// ============================================

async function loadCameras() {
    if (camerasLoading || !cameraListElem) return;
    
    camerasLoading = true;
    cameraListElem.innerHTML = '<div class="loading">Загрузка списка камер...</div>';
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch('/api/cameras', { 
            signal: controller.signal 
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        renderMainCamerasList(data);
        
    } catch (error) {
        console.error('Ошибка загрузки камер:', error);
        
        // Fallback - показываем только текущую камеру
        cameraListElem.innerHTML = `
            <div class="camera-item-row current">
                <div class="radio-container">
                    <label class="custom-radio">
                        <input type="radio" name="camera" class="camera-radio" 
                               value="/dev/video0" checked
                               onchange="selectMainCamera('/dev/video0')">
                        <span class="radio-indicator radio-green"></span>
                        <span class="radio-text radio-green">✓ Активна</span>
                    </label>
                </div>
                <div class="camera-info">
                    <div class="camera-name-main">Текущая камера</div>
                    <div class="camera-details">
                        <span class="camera-device-main">/dev/video0</span>
                    </div>
                </div>
            </div>
            <div class="error" style="margin-top: 10px;">
                Не удалось загрузить полный список камер
            </div>
        `;
    } finally {
        camerasLoading = false;
    }
}

function renderMainCamerasList(data) {
    if (!cameraListElem) return;
    
    if (!data.cameras || data.cameras.length === 0) {
        cameraListElem.innerHTML = '<div class="error">Камеры не найдены</div>';
        return;
    }
    
    let html = '';
    
    data.cameras.forEach(camera => {
        const isCurrent = camera.is_current;
        
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
        
        // Определяем цвет радиокнопки
        const radioColor = isCurrent ? 'radio-green' : 'radio-red';
        const radioText = isCurrent ? '✓ Активна' : 'Выбрать';
        
        html += `
            <div class="camera-item-row ${isCurrent ? 'current' : ''}">
                <div class="radio-container">
                    <label class="custom-radio">
                        <input type="radio" name="camera" class="camera-radio" 
                               value="${camera.device_path}" ${isCurrent ? 'checked' : ''} 
                               onchange="selectMainCamera('${camera.device_path}')">
                        <span class="radio-indicator ${radioColor}"></span>
                        <span class="radio-text ${radioColor}">${radioText}</span>
                    </label>
                </div>
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
                    <button class="btn-apply ${isCurrent ? 'disabled' : ''}" 
                            onclick="applyCamera('${camera.device_path}')"
                            ${isCurrent ? 'disabled' : ''}>
                        Применить
                    </button>
                </div>
            </div>
        `;
    });
    
    cameraListElem.innerHTML = html;
}

function selectMainCamera(devicePath) {
    const items = document.querySelectorAll('.camera-item-row');
    let foundCurrent = false;
    
    items.forEach(item => {
        const radio = item.querySelector('.camera-radio');
        const radioIndicator = item.querySelector('.radio-indicator');
        const radioText = item.querySelector('.radio-text');
        
        if (radio.value === devicePath) {
            item.classList.add('selected');
            if (!radio.checked) { // Если это не текущая камера
                radioIndicator.classList.remove('radio-green', 'radio-red');
                radioIndicator.classList.add('radio-red');
                radioText.classList.remove('radio-green', 'radio-red');
                radioText.classList.add('radio-red');
                radioText.textContent = 'Выбрать';
            }
        } else {
            item.classList.remove('selected');
            if (!radio.checked) { // Если это не текущая камера
                radioIndicator.classList.remove('radio-green', 'radio-red');
                radioIndicator.classList.add('radio-red');
                radioText.classList.remove('radio-green', 'radio-red');
                radioText.classList.add('radio-red');
                radioText.textContent = 'Выбрать';
            }
        }
        
        // Отмечаем текущую камеру
        if (radio.checked) {
            foundCurrent = true;
            radioIndicator.classList.remove('radio-green', 'radio-red');
            radioIndicator.classList.add('radio-green');
            radioText.classList.remove('radio-green', 'radio-red');
            radioText.classList.add('radio-green');
            radioText.textContent = '✓ Активна';
        }
    });
}

async function applyCamera(devicePath) {
    const btn = event.target;
    const originalText = btn.textContent;
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
            console.log('✅ Камера успешно изменена на ' + result.device_path);
            
            // Обновляем список камер
            setTimeout(() => {
                loadCameras();
                updateCameraStatus();
            }, 1000);
            
            // Обновляем текущую камеру в статусе
            if (currentCameraElem) {
                currentCameraElem.textContent = result.device_path;
            }
            
            // Если стрим был активен и его перезапустили
            if (result.stream_active && streamActive) {
                setTimeout(() => {
                    // Принудительно обновляем видеопоток
                    if (videoImg && streamActive) {
                        videoImg.src = '/video_feed?' + Date.now();
                        connectionStatus.textContent = '🔄 Обновление...';
                    }
                }, 1000);
            }
        } else {
            console.error('❌ Ошибка изменения камеры: ' + result.message);
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (error) {
        console.error('Ошибка API:', error);
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================

function checkStreamConnection() {
    if (!streamActive) return;
    
    if (videoImg && videoImg.complete && videoImg.naturalWidth > 0) {
        connectionStatus.textContent = '✅ Подключено';
        connectionAttempts = 0;
    } else {
        connectionAttempts++;
        console.log('Проверка подключения, попытка:', connectionAttempts);
        
        if (connectionAttempts < 3) {
            setTimeout(() => {
                if (videoImg && streamActive) {
                    videoImg.src = '/video_feed?' + Date.now();
                }
            }, 1000);
        } else {
            connectionStatus.textContent = '❌ Ошибка подключения';
            alert('⚠️ Не удалось подключиться к видеопотоку. Проверьте камеру и перезапустите стрим.');
        }
    }
}

function refreshStream() {
    if (streamActive && videoImg) {
        console.log('Обновление видеопотока...');
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

async function updateStatus() {
    try {
        const response = await fetch('/api/stream/status');
        const status = await response.json();
        
        if (frameCountDisplay) {
            frameCountDisplay.textContent = status.frame_count;
        }
        
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
        
        if (currentCameraElem) {
            currentCameraElem.textContent = status.camera_device || 'Неизвестно';
        }
        
        if (cameraReadyStatusElem) {
            const indicator = cameraReadyStatusElem.querySelector('.status-indicator');
            const text = cameraReadyStatusElem.querySelector('strong');
            
            if (indicator && text) {
                if (status.camera_ready) {
                    indicator.className = 'status-indicator active';
                    text.textContent = '✅ Готова';
                } else {
                    indicator.className = 'status-indicator inactive';
                    text.textContent = '❌ Не готова';
                }
            }
        }
        
    } catch (error) {
        console.error('Ошибка обновления статуса камеры:', error);
    }
}

// ============================================
// МОДАЛЬНОЕ ОКНО ДЛЯ ВЫБОРА КАМЕРЫ
// ============================================

async function showCameras() {
    const modal = document.getElementById('camera-modal');
    const content = document.getElementById('camera-modal-content');
    
    if (!modal || !content) return;
    
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
    const modal = document.getElementById('camera-modal');
    if (modal) {
        modal.style.display = 'none';
        selectedCamera = null;
        const selectBtn = document.getElementById('select-camera-btn');
        if (selectBtn) selectBtn.disabled = true;
    }
}

function renderCamerasList(data) {
    const content = document.getElementById('camera-modal-content');
    if (!content) return;
    
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
        if (item.onclick && item.onclick.toString().includes(devicePath)) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
    
    const selectBtn = document.getElementById('select-camera-btn');
    if (selectBtn) selectBtn.disabled = false;
}

async function selectCamera() {
    if (!selectedCamera) {
        alert('Пожалуйста, выберите камеру');
        return;
    }
    
    const btn = document.getElementById('select-camera-btn');
    if (!btn) return;
    
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

// ============================================
// УТИЛИТЫ
// ============================================

async function forceStartStream() {
    console.log('⚡ Принудительный запуск стрима...');
    
    // Сбрасываем счетчики
    streamActive = false;
    connectionAttempts = 0;
    
    // Останавливаем текущий стрим если есть
    await stopStream();
    
    // Ждем 500ms
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Запускаем стрим
    await startStream();
}

function refreshCameras() {
    if (!camerasLoading) {
        loadCameras();
    }
}

// Экспортируем функции для использования в HTML
window.startStream = startStream;
window.stopStream = stopStream;
window.checkCamera = checkCamera;
window.refreshStream = refreshStream;
window.restartStream = restartStream;
window.showCameras = showCameras;
window.closeCameras = closeCameras;
window.selectCamera = selectCamera;
window.selectCameraItem = selectCameraItem;
window.selectMainCamera = selectMainCamera;
window.applyCamera = applyCamera;
window.forceStartStream = forceStartStream;
window.refreshCameras = refreshCameras;

console.log('📦 app.js загружен и готов к работе');