// ----------------- app.js -------------------------------------------------
class StreamController {
    constructor() {
        // Основные свойства
        this.isStreamActive = false;
        this.currentDevicePath = null;
        this.cameraType = 'v4l2';
        
        // Элементы DOM
        this.videoElement = document.getElementById('video-stream');
        
        // Флаги для защиты от бесконечных вызовов
        this.isCheckingStatus = false;
        this.isLoadingCameras = false;
        this.lastStatusCheck = 0;
        this.lastCameraLoad = 0;
        
        // Таймеры
        this.statusInterval = null;
        this.videoRefreshTimer = null;
        
        // Инициализация с защитой
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
    
    // renderCameraList(cameras) {
    //     const container = document.getElementById('camera-list');
    //     if (!container) return;
        
    //     if (!cameras || cameras.length === 0) {
    //         container.innerHTML = '<div class="no-cameras">Камеры не найдены</div>';
    //         return;
    //     }
        
    //     console.log('📋 Рендеринг списка камер:', {
    //         total: cameras.length,
    //         currentDevice: this.currentDevicePath,
    //         cameras: cameras.map(c => ({ 
    //             path: c.device_path, 
    //             name: c.name, 
    //             type: c.type,
    //             formats: c.formats 
    //         }))
    //     });
        
    //     // Группируем камеры по типу
    //     const usbCameras = cameras.filter(c => {
    //         const type = (c.type || '').toUpperCase();
    //         return type === 'USB' || type === 'V4L2' || !type.includes('CSI');
    //     });
        
    //     const csiCameras = cameras.filter(c => {
    //         const type = (c.type || '').toUpperCase();
    //         return type.includes('CSI') || type === 'MMAL';
    //     });
        
    //     console.log('📊 Группы камер:', {
    //         usb: usbCameras.length,
    //         csi: csiCameras.length
    //     });
        
    //     let html = '';
        
    //     // Показываем CSI камеры первыми
    //     if (csiCameras.length > 0) {
    //         html += '<div class="camera-group-title">CSI Камеры</div>';
    //         csiCameras.forEach(camera => {
    //             html += this.renderCameraCard(camera);
    //         });
    //     }
        
    //     // Потом USB камеры
    //     if (usbCameras.length > 0) {
    //         html += '<div class="camera-group-title">USB Камеры</div>';
    //         usbCameras.forEach(camera => {
    //             html += this.renderCameraCard(camera);
    //         });
    //     }
        
    //     // Если ни одной камеры не найдено
    //     if (!html) {
    //         html = '<div class="no-cameras-message">Камеры не найдены</div>';
    //     }
        
    //     container.innerHTML = html;
    // }

    // Временно замените renderCameraList на это:
    // renderCameraList(cameras) {
    //     const container = document.getElementById('camera-list');
    //     if (!container) return;
        
    //     if (!cameras || cameras.length === 0) {
    //         container.innerHTML = '<div class="no-cameras">Камеры не найдены</div>';
    //         return;
    //     }
        
    //     // Выводим ВСЕ камеры без фильтрации
    //     let html = '<div class="camera-group-title">Все камеры (отладка)</div>';
    //     cameras.forEach(camera => {
    //         html += `
    //             <div style="background: rgba(255,255,255,0.1); padding: 10px; margin: 5px 0; border-radius: 5px;">
    //                 Путь: ${camera.device_path}<br>
    //                 Имя: ${camera.name || 'нет'}<br>
    //                 Тип: ${camera.type || 'не указан'}<br>
    //                 Форматы: ${camera.formats?.join(', ') || 'нет'}
    //             </div>
    //         `;
    //     });
        
    //     container.innerHTML = html;
    // }


    // renderCameraList(cameras) {
    //     const container = document.getElementById('camera-list');
    //     if (!container) return;
        
    //     if (!cameras || cameras.length === 0) {
    //         container.innerHTML = '<div class="no-cameras">Камеры не найдены</div>';
    //         return;
    //     }
        
    //     console.log('📋 ВСЕ камеры для отладки:', cameras);
        
    //     // Выводим ВСЕ камеры без фильтрации
    //     let html = '<div class="camera-group-title">Все камеры (отладка)</div>';
    //     cameras.forEach((camera, index) => {
    //         const isSelected = camera.device_path === this.currentDevicePath;
    //         html += `
    //             <div style="
    //                 background: ${isSelected ? 'rgba(72, 187, 120, 0.2)' : 'rgba(255,255,255,0.1)'}; 
    //                 padding: 10px; 
    //                 margin: 5px 0; 
    //                 border-radius: 5px;
    //                 border-left: 4px solid ${isSelected ? '#48bb78' : '#4a5568'};
    //             ">
    //                 <strong>${index + 1}. ${camera.device_path}</strong>
    //                 ${isSelected ? ' <span style="color: #48bb78;">(Текущая)</span>' : ''}<br>
    //                 Имя: ${camera.name || 'нет'}<br>
    //                 Тип: "${camera.type || 'не указан'}"<br>
    //                 Форматы: ${camera.formats?.join(', ') || 'нет'}
    //             </div>
    //         `;
    //     });
        
    //     container.innerHTML = html;
    // }    

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

    // renderCameraCard(camera) {
    //     const isSelected = camera.device_path === this.currentDevicePath;
        
    //     // Определяем тип камеры
    //     let cameraType = camera.type || 'USB';
    //     const typeUpper = cameraType.toUpperCase();
        
    //     if (typeUpper.includes('CSI') || typeUpper === 'MMAL') {
    //         cameraType = 'CSI';
    //     } else if (typeUpper === 'USB' || typeUpper === 'V4L2' || !typeUpper.includes('CSI')) {
    //         cameraType = 'USB';
    //     }
        
    //     // Упрощаем название камеры
    //     let cameraName = camera.name || camera.device_path;
    //     cameraName = cameraName
    //         .replace(/\(usb-[^)]+\)/g, '')
    //         .replace(/\(046d:0825\)/g, '')
    //         .replace(/:/g, '')
    //         .trim();
        
    //     if (cameraName.length > 25) {
    //         cameraName = cameraName.substring(0, 22) + '...';
    //     }
        
    //     // Определяем иконку
    //     const icon = cameraType === 'CSI' ? '📷' : '🔌';
    //     const typeClass = cameraType.toLowerCase();
        
    //     // Безопасное создание HTML
    //     const escapedName = this.escapeHtml(cameraName);
    //     const escapedPath = this.escapeHtml(camera.device_path);
    //     const escapedType = this.escapeHtml(cameraType);
        
    //     return `
    //         <div class="camera-card ${isSelected ? 'selected' : ''}" 
    //             data-device-path="${escapedPath}"
    //             onclick="handleCameraChange('${escapedPath.replace(/'/g, "\\'")}')"
    //             title="${escapedName} (${escapedType}) - ${escapedPath}">
    //             <div class="camera-selector">
    //                 <div class="selection-square ${isSelected ? 'selected' : ''}">
    //                     ${isSelected ? '✓' : ''}
    //                 </div>
    //                 <div class="camera-info">
    //                     <div class="camera-header">
    //                         <span class="camera-icon">${icon}</span>
    //                         <span class="camera-name">${escapedName}</span>
    //                         <span class="camera-type-badge ${typeClass}">
    //                             ${escapedType}
    //                         </span>
    //                         ${isSelected ? '<span class="current-badge">Текущая</span>' : ''}
    //                     </div>
    //                     <div class="camera-path">${escapedPath}</div>
    //                 </div>
    //             </div>
    //         </div>
    //     `;
    // }

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
            // Можно добавить логику для красивых имен
            // Например: "Logitech Webcam (/dev/video4)"
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
let streamController = null;

// Инициализация после полной загрузки страницы
document.addEventListener('DOMContentLoaded', () => {
    // Небольшая задержка для полной загрузки стилей
    setTimeout(() => {
        if (!streamController) {
            streamController = new StreamController();
            console.log('✅ StreamController инициализирован');
        }
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
        } else {
            console.error('❌ Ошибка смены камеры:', data.message);
        }
        
    } catch (error) {
        console.error('❌ Ошибка смены камеры:', error);
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


// Функция создания снимка (без всплывающих окон)
async function takePicture() {
    const btn = document.querySelector('.btn-capture-full');
    const originalText = btn.innerHTML;
    
    try {
        // Меняем состояние кнопки
        btn.innerHTML = '📸 Сохранение...';
        btn.disabled = true;
        
        console.log('📸 Отправка запроса на создание снимка...');
        
        // Отправляем запрос
        const response = await fetch('/api/camera/capture', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('✅ Снимок успешно сохранен:', data);
            
            // Просто меняем текст кнопки на успех
            btn.innerHTML = '✅ Готово!';
            btn.style.background = 'linear-gradient(135deg, #38a169, #68d391)';
            
            // Через 1.5 секунды возвращаем исходный вид
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.background = 'linear-gradient(135deg, #8a2be2, #9370db)';
            }, 1500);
            
        } else {
            console.error('❌ Ошибка от сервера:', data.message);
            
            // Показываем ошибку на кнопке
            btn.innerHTML = '❌ Ошибка';
            btn.style.background = 'linear-gradient(135deg, #e53e3e, #fc8181)';
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.background = 'linear-gradient(135deg, #8a2be2, #9370db)';
            }, 1500);
        }
        
    } catch (error) {
        console.error('❌ Ошибка при создании снимка:', error);
        
        // Показываем ошибку на кнопке
        btn.innerHTML = '❌ Ошибка сети';
        btn.style.background = 'linear-gradient(135deg, #e53e3e, #fc8181)';
        
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.background = 'linear-gradient(135deg, #8a2be2, #9370db)';
        }, 1500);
        
    } finally {
        // Разблокируем кнопку (после таймаута)
        setTimeout(() => {
            btn.disabled = false;
        }, 1500);
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
// Обработчики видео
function onVideoLoad() {
    console.log('✅ Видео загружено');
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'none';
}

function onVideoError() {
    console.log('❌ Ошибка загрузки видео');
    const placeholder = document.getElementById('video-placeholder');
    if (placeholder) placeholder.style.display = 'flex';
}

// Очистка при закрытии страницы
window.addEventListener('beforeunload', () => {
    if (streamController) {
        streamController.destroy();
    }
});

//=================  temp =======================================

// Показываем/скрываем секцию фотографий
function togglePhotosSection(show = true) {
    const section = document.getElementById('photos-preview-section');
    if (section) {
        section.style.display = show ? 'block' : 'none';
    }
}

// Автоматически показываем секцию при загрузке
document.addEventListener('DOMContentLoaded', function() {
    // Показываем секцию через 2 секунды
    setTimeout(() => {
        togglePhotosSection(true);
    }, 2000);
});