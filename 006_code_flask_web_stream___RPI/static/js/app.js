// ----------------- app.js -------------------------------------------------

// Глобальные обработчики видео
window.videoErrorCount = 0;
window.MAX_VIDEO_ERRORS = 5;

window.onVideoLoad = function() {
    console.log('✅ Видео загружено');
    window.videoErrorCount = 0; // Сбрасываем счетчик ошибок
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
        placeholder.style.opacity = '0';
    }
    
    // Убираем обработчик ошибок после успешной загрузки
    const video = document.getElementById('video-stream');
    if (video) {
        video.onerror = null;
    }
};

window.onVideoError = function() {
    window.videoErrorCount++;
    console.log(`❌ Ошибка загрузки видео (${window.videoErrorCount}/${window.MAX_VIDEO_ERRORS})`);
    
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) {
        placeholder.style.display = 'flex';
        placeholder.style.opacity = '1';
    }
    
    // Если слишком много ошибок - не пытаемся дальше
    if (window.videoErrorCount >= window.MAX_VIDEO_ERRORS) {
        console.log('⚠️ Превышено максимальное количество ошибок видео');
        return;
    }
    
    // Пытаемся восстановить через 2 секунды
    setTimeout(() => {
        if (window.streamController && window.streamController.isStreamActive) {
            console.log('🔄 Пытаюсь восстановить видео...');
            window.streamController.refreshVideo();
        }
    }, 2000);
};

class StreamController {
    constructor() {
        // === ПАТТЕРН СИНГЛТОН ===
        if (window.__streamControllerInstance) {
            console.log('⚠️ StreamController уже создан, возвращаю существующий экземпляр');
            return window.__streamControllerInstance;
        } 
        
        window.__streamControllerInstance = this;

        console.log('🛠️ === КОНСТРУКТОР StreamController ВЫЗВАН ===');
        
        // Определяем обновление страницы
        this.isPageRefresh = performance.navigation?.type === 1;
        console.log('📊 Страница:', this.isPageRefresh ? 'ОБНОВЛЕНИЕ' : 'НОВАЯ');
        
        // Основные свойства
        this.isStreamActive = false;
        this.currentDevicePath = null;
        this.cameraType = null;
        this._autoStartCalled = false;
        this._videoInitialized = false;
        
        // Конфигурация
        this.config = {
            stream: { auto_start: true },
            camera: { device: '/dev/video4' }
        };
        
        console.log('✅ АВТОЗАПУСК ВКЛЮЧЕН');
        
        // Элементы DOM
        this.videoElement = document.getElementById('video-stream');
        
        // Сбрасываем счетчик ошибок
        window.videoErrorCount = 0;
        
        // Инициализируем видео
        this.initVideoElement();
        
        // Флаги
        this.isCheckingStatus = false;
        this.isLoadingCameras = false;
        this.lastStatusCheck = 0;
        this.lastCameraLoad = 0;
        
        // Таймеры
        this.statusInterval = null;
        this.videoRefreshTimer = null;
        
        // Сразу активируем UI
        this.activateUIElements();
        
        // Запускаем инициализацию с задержкой
        const initDelay = this.isPageRefresh ? 3000 : 1000;
        console.log(`⏳ Инициализация через ${initDelay}мс...`);
        
        setTimeout(() => {
            this.init().then(() => {
                console.log('✅ Инициализация завершена');
                this.scheduleAutoStart();
            }).catch(error => {
                console.error('❌ Ошибка инициализации:', error);
                this.scheduleAutoStart();
            });
        }, initDelay);
    }
    
    // Добавьте этот метод для инициализации видео элемента
    // ДОБАВЬТЕ ЭТОТ МЕТОД СРАЗУ ПОСЛЕ КОНСТРУКТОРА:
    initVideoElement() {
        console.log('🎬 initVideoElement вызван');
        
        // Находим элемент
        this.videoElement = document.getElementById('video-stream');
        
        if (!this.videoElement) {
            console.error('❌ Элемент video-stream не найден в DOM');
            return;
        }
        
        console.log('📊 Обнаружен элемент:', {
            tagName: this.videoElement.tagName,
            id: this.videoElement.id,
            isIMG: this.videoElement.tagName === 'IMG',
            isVIDEO: this.videoElement.tagName === 'VIDEO'
        });
        
        // Работаем в зависимости от типа элемента
        if (this.videoElement.tagName === 'IMG') {
            console.log('ℹ️ Работаю с IMG элементом');
            
            // Для IMG просто устанавливаем обработчики
            this.videoElement.onload = window.onVideoLoad;
            this.videoElement.onerror = window.onVideoError;
            
            this._videoInitialized = true;
            console.log('✅ IMG элемент инициализирован');
            
        } else if (this.videoElement.tagName === 'VIDEO') {
            console.log('✅ Работаю с VIDEO элементом');
            
            // Устанавливаем атрибуты для VIDEO
            this.videoElement.autoplay = true;
            this.videoElement.playsinline = true;
            this.videoElement.muted = true;
            this.videoElement.setAttribute('webkit-playsinline', 'true');
            this.videoElement.preload = 'auto';
            
            this.videoElement.onloadeddata = window.onVideoLoad;
            this.videoElement.onerror = window.onVideoError;
            
            this._videoInitialized = true;
            console.log('✅ VIDEO элемент инициализирован');
            
        } else {
            console.error(`❌ Неподдерживаемый элемент: ${this.videoElement.tagName}`);
        }
    }
    
    // Добавьте этот метод после initVideoElement
    checkVideoElement() {
        if (!this.videoElement) {
            this.videoElement = document.getElementById('video-stream');
        }
        
        if (!this.videoElement) {
            console.error('❌ Элемент video-stream не найден');
            return false;
        }
        
        // Принимаем как IMG так и VIDEO
        if (this.videoElement.tagName !== 'IMG' && this.videoElement.tagName !== 'VIDEO') {
            console.error(`❌ Неподдерживаемый тип элемента: ${this.videoElement.tagName}`);
            return false;
        }
        
        console.log(`✅ Элемент корректен: ${this.videoElement.tagName}`);
        return true;
    } 
        
    // Активация элементов UI
    activateUIElements() {
        console.log('🎨 Активация элементов UI...');
        
        // Активируем видео элемент
        if (this.videoElement) {
            this.videoElement.style.pointerEvents = 'auto';
            this.videoElement.style.opacity = '1';
        }
        
        // Активируем кнопки
        setTimeout(() => {
            document.querySelectorAll('button, select, input, .btn').forEach(el => {
                el.disabled = false;
                el.style.pointerEvents = 'auto';
                el.style.opacity = '1';
            });
            
            // Специально активируем кнопки управления стримом
            ['start-btn', 'stop-btn', 'refresh-btn'].forEach(id => {
                const btn = document.getElementById(id);
                if (btn) {
                    btn.disabled = false;
                    btn.style.pointerEvents = 'auto';
                    btn.style.opacity = '1';
                    btn.classList.remove('disabled');
                }
            });
        }, 100);
    }
    
    // Планирование автостарта
    scheduleAutoStart() {
        console.log('⏰ Планирование автостарта...');
        
        if (this._autoStartCalled) {
            console.log('⏸️ Автостарт уже запланирован');
            return;
        }
        
        const delay = this.isPageRefresh ? 4000 : 1000;
        console.log(`⏳ Запуск через ${delay}мс...`);
        
        setTimeout(() => {
            console.log('▶️ Запускаю автостарт...');
            this._autoStartCalled = true;
            this.handleAutoStart();
        }, delay);
    }

    
    // Мониторинг UI
    startUIMonitoring() {
        // Останавливаем предыдущий мониторинг
        if (this.uiMonitorInterval) {
            clearInterval(this.uiMonitorInterval);
        }
        
        // Проверяем UI каждые 2 секунды
        this.uiMonitorInterval = setInterval(() => {
            const disabledElements = document.querySelectorAll('button[disabled], select[disabled], input[disabled]');
            if (disabledElements.length > 3) {
                console.warn(`⚠️ Обнаружено ${disabledElements.length} заблокированных элементов, активирую...`);
                this.activateUIElements();
            }
        }, 2000);
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


    // Добавьте в класс после scheduleAutoStart()
    attemptReconnect() {
        if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
            console.error('❌ Превышено максимальное количество попыток восстановления');
            this.showToast('Не удалось восстановить стрим. Перезагрузите страницу.', 'error');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectAttempts * 3000;
        
        console.log(`🔄 Попытка восстановления ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS} через ${delay}мс`);
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        this.reconnectTimer = setTimeout(async () => {
            console.log('🔄 Выполняю восстановление соединения...');
            try {
                await this.startStream();
                console.log('✅ Соединение восстановлено!');
                this.reconnectAttempts = 0;
            } catch (error) {
                console.error('❌ Ошибка восстановления:', error);
                this.attemptReconnect();
            }
        }, delay);
    }

    // === ДОБАВЬТЕ ЭТОТ МЕТОД В КЛАСС ===
    async handleAutoStart() {
        console.log('🎯 Запуск автостарта...');
        
        if (this._autoStartCalled && this._streamRestorationAttempted) {
            console.log('⏸️ handleAutoStart уже был вызван');
            return;
        }
        
        if (this.config?.stream?.auto_start && !this.isStreamActive) {
            console.log('🚀 Запускаю стрим...');
            
            // Дополнительная задержка при обновлении
            if (this.isPageRefresh && !this._streamRestorationAttempted) {
                console.log('🔄 Обновление страницы, жду 3 секунды...');
                await new Promise(resolve => setTimeout(resolve, 3000));
                this._streamRestorationAttempted = true;
            }
            
            try {
                await this.startStream();
                console.log('✅ Автозапуск выполнен');
            } catch (error) {
                console.error('❌ Ошибка автостарта:', error);
            }
        } else {
            console.log('⏸️ Автозапуск не требуется', {
                auto_start: this.config?.stream?.auto_start,
                isStreamActive: this.isStreamActive
            });
        }
    }

    // Временный метод для прямого запуска
    async directAutoStart() {
        console.log('🚨 ПРЯМОЙ АВТОЗАПУСК (обходной путь)');
        
        try {
            console.log('🔍 Проверяю статус сервера...');
            const response = await fetch('/api/stream/status');
            const data = await response.json();
            
            console.log('📊 Статус сервера:', data);
            
            if (!data.stream_active) {
                console.log('▶️ Запускаю стрим...');
                const startResponse = await fetch('/api/stream/start', { method: 'POST' });
                const startData = await startResponse.json();
                
                console.log('✅ Результат запуска:', startData);
                
                // Обновляем UI
                if (startData.status === 'started' || startData.status === 'already_running') {
                    this.updateUI(true);
                    console.log('✅ Стрим запущен!');
                }
            } else {
                console.log('✅ Стрим уже активен');
                this.updateUI(true);
            }
            
        } catch (error) {
            console.error('❌ Ошибка прямого автозапуска:', error);
        }
    }    
    
    async init() {
        try {
            console.log('🚀 Инициализация StreamController...');
            
            // Сначала проверяем статус сервера
            await this.checkStatus();
            
            // Затем загружаем камеры (если сервер доступен)
            if (this.currentDevicePath) {
                await this.loadCameras();
            }
            
            // Запускаем обновление статуса с интервалом
            this.startStatusUpdates();
            
            // Запускаем мониторинг UI
            this.startUIMonitoring();
            
        } catch (error) {
            console.error('❌ Ошибка инициализации:', error);
            this.showErrorMessage('Ошибка подключения к серверу');
        }
    }

    async loadCameras() {
        // ЗАЩИТА: предотвращаем одновременные запросы
        if (this.isLoadingCameras) {
            console.log('⏸️ Загрузка камер уже выполняется, пропускаем...');
            return;
        }
        
        // ЗАЩИТА: минимальный интервал между запросами (5 секунд)
        const now = Date.now();
        if (now - this.lastCameraLoad < 5000) {
            return;
        }
        
        this.isLoadingCameras = true;
        this.lastCameraLoad = now;
        
        try {
            console.log('🔄 Загрузка списка камер...');
            
            const response = await fetch('/api/cameras', {
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ошибка: ${response.status}`);
            }
            
            const data = await response.json();

            // ОТЛАДКА: детальный вывод ВСЕХ полей каждой камеры
            console.log('🔍 Детальная информация о камерах:');            
            if (data.cameras && Array.isArray(data.cameras)) {
                data.cameras.forEach((cam, idx) => {
                    console.log(`Камера ${idx}:`, {
                        device_path: cam.device_path,
                        name: cam.name,
                        type: cam.type,
                        is_camera: cam.is_camera,
                        is_current: cam.is_current,
                        formats: cam.formats,
                        resolutions: cam.resolutions,
                        // Все остальные поля
                        ...Object.keys(cam).reduce((acc, key) => {
                            if (!['device_path', 'name', 'type', 'is_camera', 'is_current', 'formats', 'resolutions'].includes(key)) {
                                acc[key] = cam[key];
                            }
                            return acc;
                        }, {})
                    });
                });
            }
            
            // Определяем текущее устройство
            if (data.current_device) {
                await this.determineCurrentDevice(data.current_device, data.current_camera_type);
            }
            
            // Рендерим список камер
            if (data.cameras && data.cameras.length > 0) {
                this.renderCameraList(data.cameras);
            } else {
                this.showNoCamerasMessage();
            }
            
        } catch (error) {
            console.error('❌ Ошибка загрузки камер:', error);
            this.showErrorMessage('Ошибка загрузки камер: ' + error.message);
            
        } finally {
            this.isLoadingCameras = false;
        }
    }
    
    async determineCurrentDevice(deviceId, cameraType = 'v4l2') {
        if (!deviceId || deviceId === 'undefined' || deviceId === 'null') {
            console.warn('⚠️ deviceId не определен, используем /dev/video0');
            this.currentDevicePath = '/dev/video0';
            this.cameraType = 'v4l2';
            return;
        }
        
        // Очищаем
        const cleanDeviceId = String(deviceId).trim();
        
        // Обработка CSI камер
        if (cleanDeviceId.startsWith('csi_')) {
            this.currentDevicePath = cleanDeviceId;
            this.cameraType = 'csi';
            console.log(`🎯 CSI камера: ${cleanDeviceId}`);
        }
        // Обработка V4L2 камер
        else if (cleanDeviceId.startsWith('/dev/video')) {
            this.currentDevicePath = cleanDeviceId;
            this.cameraType = 'v4l2';
            console.log(`🎯 V4L2 камера: ${cleanDeviceId}`);
        }
        // Обработка других форматов
        else if (/^\d+$/.test(cleanDeviceId)) {
            this.currentDevicePath = `/dev/video${cleanDeviceId}`;
            this.cameraType = 'v4l2';
            console.log(`🎯 Камера по номеру: ${cleanDeviceId} → ${this.currentDevicePath}`);
        }
        // Любая другая строка
        else {
            this.currentDevicePath = cleanDeviceId;
            this.cameraType = cameraType || 'v4l2';
            console.log(`🎯 Другая камера: ${cleanDeviceId} (тип: ${this.cameraType})`);
        }
        
        console.log(`✅ Установлена камера: ${this.currentDevicePath}, тип: ${this.cameraType}`);
    }

    renderCameraList(cameras) {
        const container = document.getElementById('camera-list');
        if (!container) return;
        
        if (!cameras || cameras.length === 0) {
            container.innerHTML = '<div class="no-cameras">Камеры не найдены</div>';
            return;
        }
        
        console.log('📋 ВСЕ камеры для отладки:', cameras);
        
        // ОТЛАДКА: посмотрим, какие типы есть у камер
        cameras.forEach((cam, idx) => {
            console.log(`Камера ${idx}:`, {
                path: cam.device_path,
                type: cam.type || 'не указан',
                name: cam.name,
                is_current: cam.is_current
            });
        });
        
        // ФИЛЬТРАЦИЯ: теперь правильно определяем типы
        const v4l2Cameras = cameras.filter(c => {
            // V4L2 камеры: путь начинается с /dev/video
            return c.device_path && c.device_path.startsWith('/dev/video');
        });
        
        const csiCameras = cameras.filter(c => {
            // CSI камеры: путь начинается с csi_ или тип содержит CSI
            return (c.device_path && c.device_path.startsWith('csi_')) ||
                (c.type && c.type.toLowerCase().includes('csi'));
        });
        
        console.log('📊 Группы камер (исправлено):', {
            v4l2: v4l2Cameras.length,
            csi: csiCameras.length,
            total: cameras.length
        });
        
        let html = '';
        
        // CSI камеры (если есть)
        if (csiCameras.length > 0) {
            html += '<div class="camera-group-title">CSI Камеры</div>';
            csiCameras.forEach(camera => {
                html += this.renderCameraCard(camera);
            });
        }
        
        // V4L2 камеры (USB)
        if (v4l2Cameras.length > 0) {
            html += '<div class="camera-group-title">V4L2 Камеры (USB)</div>';
            v4l2Cameras.forEach(camera => {
                html += this.renderCameraCard(camera);
            });
        }
        
        container.innerHTML = html;
    }

    renderCameraCard(camera) {
        const isSelected = camera.device_path === this.currentDevicePath;
        
        // Определяем тип камеры по пути ИЛИ по полю type
        let cameraType = 'USB';
        let icon = '🔌';
        
        // Определяем по пути (основной способ)
        if (camera.device_path.startsWith('csi_')) {
            cameraType = 'CSI';
            icon = '📷';
        } else if (camera.device_path.startsWith('/dev/video')) {
            cameraType = 'V4L2';
            icon = '🔌';
        }
        
        // Переопределяем по полю type, если оно есть
        if (camera.type) {
            const typeLower = camera.type.toLowerCase();
            if (typeLower.includes('csi')) {
                cameraType = 'CSI';
                icon = '📷';
            } else if (typeLower.includes('usb') || typeLower.includes('v4l2')) {
                cameraType = 'USB';
                icon = '🔌';
            }
        }
        
        // Упрощаем название камеры
        let cameraName = camera.name || camera.device_path;
        
        // Если это V4L2 камера и есть имя - используем его
        if (cameraName.startsWith('/dev/video')) {
            cameraName = `Камера ${camera.device_path}`;
        }
        
        // Очистка
        cameraName = cameraName
            .replace(/\(usb-[^)]+\)/g, '')
            .replace(/\(046d:0825\)/g, '')
            .replace(/:/g, '')
            .trim();
        
        if (cameraName.length > 25) {
            cameraName = cameraName.substring(0, 22) + '...';
        }
        
        const typeClass = cameraType.toLowerCase();
        const escapedName = this.escapeHtml(cameraName);
        const escapedPath = this.escapeHtml(camera.device_path);
        const escapedType = this.escapeHtml(cameraType);
        
        return `
            <div class="camera-card ${isSelected ? 'selected' : ''}" 
                data-device-path="${escapedPath}"
                onclick="handleCameraChange('${escapedPath.replace(/'/g, "\\'")}')"
                title="${escapedName} (${escapedType}) - ${escapedPath}">
                <div class="camera-selector">
                    <div class="selection-square ${isSelected ? 'selected' : ''}">
                        ${isSelected ? '✓' : ''}
                    </div>
                    <div class="camera-info">
                        <div class="camera-header">
                            <span class="camera-icon">${icon}</span>
                            <span class="camera-name">${escapedName}</span>
                            <span class="camera-type-badge ${typeClass}">
                                ${escapedType}
                            </span>
                            ${isSelected ? '<span class="current-badge">Текущая</span>' : ''}
                            ${camera.is_current ? '<span class="current-badge">Текущая (сервер)</span>' : ''}
                        </div>
                        <div class="camera-path">${escapedPath}</div>
                    </div>
                </div>
            </div>
        `;
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
            
            const cameraType = currentCamera.type || 'USB';
            const typeColor = cameraType === 'CSI' ? '#9370db' : '#48bb78';
            
            displayElement.innerHTML = `
                <span style="color: ${typeColor}; font-weight: bold;">${cameraName}</span>
                <span style="background: ${typeColor}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-left: 5px;">${cameraType}</span>
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
                        <button class="btn btn-sm btn-secondary" onclick="refreshCameras()" style="margin-top: 10px;">
                            🔄 Обновить список
                        </button>
                    </div>
                </div>
            `;
        }
    }

    updateCurrentCameraDisplayFromData(data) {
        const displayElement = document.getElementById('current-camera-display');
        if (!displayElement) return;
        
        if (data.camera_device) {
            let cameraName = data.camera_device;
            
            // Упрощаем отображение
            if (cameraName.length > 20) {
                cameraName = cameraName.substring(0, 17) + '...';
            }
            
            const typeColor = data.camera_type === 'CSI' ? '#9370db' : '#48bb78';
            
            displayElement.innerHTML = `
                <span style="color: ${typeColor}; font-weight: bold;">${cameraName}</span>
                <span style="background: ${typeColor}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-left: 5px;">
                    ${data.camera_type || 'USB'}
                </span>
            `;
        }
    }
    
    showErrorMessage(message) {
        const container = document.getElementById('camera-list');
        if (!container) return;
        
        container.innerHTML = `
            <div class="error-message" style="
                background: rgba(229, 62, 62, 0.1);
                border: 1px solid #e53e3e;
                border-radius: 6px;
                padding: 15px;
                text-align: center;
                color: #e53e3e;
            ">
                <div style="font-size: 24px; margin-bottom: 10px;">⚠️</div>
                <div style="margin-bottom: 10px;">${message}</div>
                <button onclick="location.reload()" style="
                    background: #e53e3e;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                ">
                    🔄 Перезагрузить
                </button>
            </div>
        `;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    async startStream() {
        try {
            console.log('▶️ Запуск стрима...');
            
            // Проверяем видео элемент
            if (!this.checkVideoElement()) {
                console.error('❌ Не могу запустить стрим: видео элемент не корректен');
                this.showToast('Ошибка видео элемента', 'error');
                return;
            }
            
            // Сбрасываем счетчик ошибок
            window.videoErrorCount = 0;
            
            const response = await fetch('/api/stream/start', { 
                method: 'POST',
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.log('🔍 Ошибка запуска:', response.status, errorText);
                
                // Если "too many streams" - ждем и пробуем снова
                if (response.status === 429 || errorText.includes('too many') || errorText.includes('уже имеет')) {
                    console.log('⏳ Обнаружено "too many streams", жду 3 секунды и пробую снова...');
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    
                    console.log('🔄 Вторая попытка запуска...');
                    const retryResponse = await fetch('/api/stream/start', { 
                        method: 'POST' 
                    });
                    
                    if (retryResponse.ok) {
                        const retryData = await retryResponse.json();
                        if (retryData.status === 'started' || retryData.status === 'already_running') {
                            this.updateUI(true);
                            console.log('✅ Стрим запущен со второй попытки');
                            
                            // Загружаем видео через 1 секунду
                            setTimeout(() => {
                                this.refreshVideo();
                            }, 1000);
                            
                            this.showToast('Стрим запущен', 'success');
                            return;
                        }
                    }
                }
                
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'started' || data.status === 'already_running') {
                this.updateUI(true);
                console.log('✅ Стрим запущен на сервере');
                
                // Даем время серверу начать генерировать кадры
                setTimeout(() => {
                    console.log('🔄 Загружаю видео поток...');
                    this.refreshVideo();
                    
                    // Вторая попытка через 2 секунды
                    setTimeout(() => {
                        if (this.videoElement && (!this.videoElement.src || this.videoElement.src === '')) {
                            console.log('⚠️ Видео не загрузилось, повторная попытка...');
                            this.refreshVideo();
                        }
                    }, 2000);
                }, 1000);
                
                this.showToast('Стрим запущен', 'success');
                
            } else {
                console.error('❌ Ошибка запуска:', data.message);
                this.showToast(`Ошибка: ${data.message}`, 'error');
            }
            
        } catch (error) {
            console.error('❌ Ошибка запуска стрима:', error);
            this.showToast('Ошибка подключения к серверу', 'error');
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
                this.showToast('Стрим остановлен', 'info');
            } else {
                console.error('❌ Ошибка остановки:', data.message);
                this.showToast(`Ошибка: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('❌ Ошибка остановки стрима:', error);
            this.showToast('Ошибка остановки стрима', 'error');
        }
    }
    
    async checkStatus() {
        // ЗАЩИТА: предотвращаем одновременные запросы
        if (this.isCheckingStatus) {
            console.log('⏸️ Проверка статуса уже выполняется, пропускаем...');
            return;
        }
        
        // ЗАЩИТА: минимальный интервал между запросами (3 секунды)
        const now = Date.now();
        if (now - this.lastStatusCheck < 3000) {
            return;
        }
        
        this.isCheckingStatus = true;
        this.lastStatusCheck = now;
        
        try {
            console.log('🔍 Проверка статуса сервера...');
            
            // Добавляем таймаут для запроса
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            
            const response = await fetch('/api/stream/status', {
                signal: controller.signal,
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Обновляем UI
            this.updateUI(data.stream_active);
            this.updateStatusInfo(data);
            
            // ВАЖНО: обновляем текущее устройство, но НЕ вызываем loadCameras()
            if (data.camera_device && data.camera_device !== this.currentDevicePath) {
                console.log('🔄 Обновление информации о текущей камере:', data.camera_device);
                this.currentDevicePath = data.camera_device;
                this.cameraType = data.camera_type || 'v4l2';
                
                // Обновляем отображение, но НЕ перезагружаем весь список
                this.updateCurrentCameraDisplayFromData(data);
            }
            
            console.log('✅ Статус обновлен:', {
                active: data.stream_active,
                frames: data.frame_count,
                camera: data.camera_device
            });
            
        } catch (error) {
            console.error('❌ Ошибка проверки статуса:', error.message);
            
            // Если сервер недоступен, увеличиваем интервал
            if (error.name === 'TypeError' || error.name === 'AbortError') {
                console.warn('⚠️ Сервер недоступен, увеличиваем интервал проверки');
                this.lastStatusCheck = Date.now() + 10000; // Ждем 10 сек
            }
            
        } finally {
            // Всегда сбрасываем флаг
            this.isCheckingStatus = false;
        }
    }
    
    updateUI(isActive) {
        this.isStreamActive = isActive;
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const statusEl = document.getElementById('stream-status');
        
        // Устанавливаем состояние кнопок
        if (startBtn) {
            startBtn.disabled = isActive;
            startBtn.classList.toggle('disabled', isActive);
            startBtn.style.opacity = isActive ? '0.5' : '1';
            startBtn.style.pointerEvents = isActive ? 'none' : 'auto';
        }
        
        if (stopBtn) {
            stopBtn.disabled = !isActive;
            stopBtn.classList.toggle('disabled', !isActive);
            stopBtn.style.opacity = !isActive ? '0.5' : '1';
            stopBtn.style.pointerEvents = !isActive ? 'none' : 'auto';
        }
        
        if (statusEl) {
            if (isActive) {
                statusEl.innerHTML = '<span class="status-indicator active"></span><strong>Активен</strong>';
            } else {
                statusEl.innerHTML = '<span class="status-indicator inactive"></span><strong>Остановлен</strong>';
            }
        }
        
        // Активно обновляем другие элементы
        this.activateUIElements();
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
        if (!this.checkVideoElement()) {
            return;
        }
        
        const newSrc = '/video_feed?nocache=' + Date.now();
        console.log(`🔄 Обновление ${this.videoElement.tagName}...`);
        
        // Для IMG просто меняем src
        if (this.videoElement.tagName === 'IMG') {
            // Сохраняем обработчики
            const oldOnLoad = this.videoElement.onload;
            const oldOnError = this.videoElement.onerror;
            
            // Устанавливаем новый src
            this.videoElement.src = newSrc;
            console.log('✅ Обновлен IMG src');
            
            // Восстанавливаем обработчики
            this.videoElement.onload = oldOnLoad;
            this.videoElement.onerror = oldOnError;
            
        } else if (this.videoElement.tagName === 'VIDEO') {
            // Для VIDEO более сложная логика
            if (!this.videoElement.paused) {
                this.videoElement.pause();
            }
            
            const oldOnLoad = this.videoElement.onloadeddata;
            const oldOnError = this.videoElement.onerror;
            
            this.videoElement.src = '';
            
            setTimeout(() => {
                this.videoElement.onloadeddata = oldOnLoad;
                this.videoElement.onerror = oldOnError;
                this.videoElement.src = newSrc;
                console.log('✅ Обновлен VIDEO src');
                
                this.videoElement.load();
                this.videoElement.play().catch(e => {
                    console.log('⚠️ Автовоспроизведение:', e.name);
                });
            }, 100);
        }
    }
        
    startStatusUpdates() {
        // Останавливаем предыдущий интервал, если есть
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
        
        // Запускаем проверку статуса каждые 5 секунд
        this.statusInterval = setInterval(() => {
            this.checkStatus();
        }, 5000);
        
        // Периодически обновляем список камер (реже)
        setInterval(() => {
            this.loadCameras();
        }, 15000); // Каждые 15 секунд
        
        console.log('🔄 Запущено автоматическое обновление');
    }
    
    // Показать уведомление
    showToast(message, type = 'info') {
        const colors = {
            success: '#48bb78',
            error: '#e53e3e',
            info: '#4299e1',
            warning: '#ed8936'
        };
        
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease;
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 300px;
            word-wrap: break-word;
        `;
        
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Автоматическое скрытие через 4 секунды
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (toast.parentNode) {
                    document.body.removeChild(toast);
                }
            }, 300);
        }, 4000);
    }
    
    destroy() {
        console.log('🧹 Очистка StreamController...');
        
        // Останавливаем все интервалы
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
        
        if (this.videoRefreshTimer) {
            clearTimeout(this.videoRefreshTimer);
            this.videoRefreshTimer = null;
        }
        
        if (this.uiMonitorInterval) {
            clearInterval(this.uiMonitorInterval);
            this.uiMonitorInterval = null;
        }
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        // Сбрасываем флаги
        this.isCheckingStatus = false;
        this.isLoadingCameras = false;
        
        // Останавливаем поток, если активен
        if (this.isStreamActive) {
            this.stopStream().catch(console.error);
        }
    }
}

// Глобальный экземпляр контроллера
let streamController = window.streamController || window.__streamControllerInstance || null;

// Функция для принудительного восстановления
function restoreStreamAfterRefresh() {
    console.log('🔄 Восстановление после обновления страницы...');
    
    setTimeout(() => {
        if (window.streamController && !window.streamController.isStreamActive) {
            console.log('🚀 Принудительный запуск стрима после обновления...');
            window.streamController.startStream().catch(err => {
                console.error('❌ Не удалось восстановить стрим:', err);
            });
        }
        
        // Активируем все элементы
        document.querySelectorAll('button, select, input').forEach(el => {
            el.disabled = false;
            el.style.pointerEvents = 'auto';
            el.style.opacity = '1';
        });
    }, 3000);
}

// Инициализация после полной загрузки страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM загружен');
    
    // Добавляем CSS анимации для уведомлений
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Небольшая задержка для полной загрузки стилей
    setTimeout(() => {
        if (!window.streamController && !window.__streamControllerInstance) {
            console.log('🔄 Инициализация StreamController после загрузки DOM...');
            window.streamController = new StreamController();
        } else {
            console.log('ℹ️ StreamController уже инициализирован');
        }
        
        // Вызываем восстановление
        restoreStreamAfterRefresh();
    }, 500);
});

// Простые обертки для кнопок
function startStream() { 
    if (streamController && !streamController.isStreamActive) {
        streamController.startStream();
    }
}

function stopStream() { 
    if (streamController && streamController.isStreamActive) {
        streamController.stopStream();
    }
}

function refreshCameras() {
    if (streamController) {
        streamController.loadCameras();
    }
}

function restartStream() {
    if (streamController) {
        console.log('🔄 Перезапуск стрима...');
        stopStream();
        setTimeout(() => {
            startStream();
        }, 1000);
    }
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
            
            // Используем handleCameraChange для обновления интерфейса
            handleCameraChange(devicePath);
        } else {
            console.error('❌ Ошибка выбора камеры:', data.message);
        }
    } catch (error) {
        console.error('❌ Ошибка выбора камеры:', error);
    }
}

// Обработка выбора камеры
async function handleCameraChange(devicePath) {
    if (!streamController || !devicePath) return;
    
    console.log(`🎯 Смена камеры на: ${devicePath}`);
    
    try {
        const response = await fetch('/api/cameras/select', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache'
            },
            body: JSON.stringify({ device_path: devicePath })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log(`✅ Камера изменена на ${devicePath}`);
            
            // Обновляем текущее устройство
            streamController.currentDevicePath = devicePath;
            
            // Перезагружаем камеры (но не сразу)
            setTimeout(() => {
                streamController.loadCameras();
            }, 500);
            
            // Если стрим был активен, обновляем видео
            if (data.stream_active) {
                setTimeout(() => {
                    streamController.refreshVideo();
                }, 1000);
            }
            
            streamController.showToast('Камера изменена', 'success');
        } else {
            console.error('❌ Ошибка смены камеры:', data.message);
            streamController.showToast(`Ошибка: ${data.message}`, 'error');
        }
        
    } catch (error) {
        console.error('❌ Ошибка смены камеры:', error);
        streamController.showToast('Ошибка смены камеры', 'error');
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
}

function onVideoError() {
    console.log('❌ Ошибка загрузки видео');
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'flex';
    
    // Пытаемся обновить видео при ошибке
    if (streamController && streamController.isStreamActive) {
        setTimeout(() => {
            streamController.refreshVideo();
        }, 2000);
    }
}

// Глобальная функция для принудительного восстановления
window.forceStreamRestore = function() {
    console.log('🚨 Ручное восстановление стрима');
    if (streamController) {
        streamController.startStream().catch(err => {
            console.error('❌ Ошибка восстановления:', err);
            alert('Не удалось восстановить стрим: ' + err.message);
        });
    }
};

// Очистка при закрытии страницы
window.addEventListener('beforeunload', () => {
    if (streamController) {
        streamController.destroy();
    }
});

// Принудительная активация при загрузке
window.addEventListener('load', () => {
    console.log('🌐 Страница полностью загружена');
    
    // Дополнительная проверка через 5 секунд
    setTimeout(() => {
        if (streamController && !streamController.isStreamActive) {
            console.log('⚠️ Стрим все еще не активен, проверяем...');
            streamController.checkStatus();
        }
    }, 5000);
});

// Глобальный экспорт для отладки
window.StreamController = StreamController;


// Глобальная функция для ручного восстановления
window.fixStreamIssue = async function() {
    console.log('🔧 Ручное исправление проблемы со стримом');
    
    if (!window.streamController) {
        alert('StreamController не инициализирован');
        return;
    }
    
    try {
        // 1. Показываем статус
        alert('Начинаю исправление проблемы "Too many streams"...');
        
        // 2. Сбрасываем соединения
        const resetResponse = await fetch('/api/stream/reset', { 
            method: 'POST' 
        });
        const resetData = await resetResponse.json();
        console.log('Сброс:', resetData);
        
        // 3. Ждем
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        // 4. Запускаем стрим
        await window.streamController.startStream();
        
        alert('✅ Проблема исправлена! Стрим должен работать.');
    } catch (error) {
        console.error('Ошибка:', error);
        alert('❌ Ошибка: ' + error.message);
    }
};

// Проверка при загрузке страницы
window.addEventListener('load', function() {
    console.log('🌐 Страница полностью загружена');
    
    // Проверяем, есть ли видео элемент
    const video = document.getElementById('video-stream');
    if (video) {
        console.log('🎬 Видео элемент найден:', {
            autoplay: video.autoplay,
            muted: video.muted,
            playsinline: video.playsinline,
            src: video.src
        });
    }
    
    // Через 5 секунд проверяем состояние
    setTimeout(() => {
        if (window.streamController && !window.streamController.isStreamActive) {
            console.log('⚠️ Стрим все еще не активен, проверяю статус...');
            window.streamController.checkStatus();
        }
    }, 5000);
});

// Добавьте кнопку в HTML для тестирования:
// <button onclick="fixStreamIssue()" style="position:fixed;bottom:20px;right:20px;z-index:10000;padding:10px;background:#e53e3e;color:white;border:none;border-radius:5px;cursor:pointer;">
//     🔧 Исправить стрим
// </button>


// В конце app.js добавьте:
window.forceCleanup = async function() {
    console.log('🧹 Принудительная очистка соединений...');
    
    try {
        // Показываем уведомление
        const notification = document.createElement('div');
        notification.innerHTML = `
            <div style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: #4299e1;
                color: white;
                padding: 20px;
                border-radius: 8px;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            ">
                <div>🧹 Очищаю соединения...</div>
            </div>
        `;
        document.body.appendChild(notification);
        
        // Ждем 3 секунды (даем время серверу на очистку)
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        // Перезагружаем страницу
        window.location.reload();
        
    } catch (error) {
        console.error('❌ Ошибка очистки:', error);
        alert('Ошибка: ' + error.message);
    }
};

// Добавьте кнопку в HTML для тестирования:
/*
<button onclick="forceCleanup()" style="
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 1000;
    padding: 10px 15px;
    background: #e53e3e;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
">
    🧹 Очистить соединения
</button>
*/