// gallery.js

// Состояние галереи
const GalleryState = {
    currentPage: 1,
    photosPerPage: 12,
    allPhotos: [],
    isLoading: false,
    hasMore: true,
    totalCount: 0,
    totalSize: '0 B'
};

// Константы
const API_ENDPOINTS = {
    LIST: '/api/photos',
    DELETE: '/api/photos/delete',
    CLEAR: '/api/photos/clear'
};

// DOM элементы
const DOM = {
    container: null,
    stats: null,
    pagination: null,
    loadMoreBtn: null,
    noPhotosMessage: null
};

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('📸 Галерея инициализируется...');
    initializeElements();
    
    // Загружаем фото через небольшую задержку
    setTimeout(loadPhotos, 500);
    
    // Автообновление каждые 30 секунд
    setInterval(loadPhotos, 30000);
});

// Инициализация DOM элементов
function initializeElements() {
    DOM.container = document.getElementById('photos-container');
    DOM.stats = document.getElementById('photos-stats');
    DOM.pagination = document.getElementById('photos-pagination');
    DOM.loadMoreBtn = document.getElementById('load-more-btn');
    DOM.noPhotosMessage = document.getElementById('no-photos-message');
    
    console.log('📸 DOM элементы инициализированы:', {
        container: !!DOM.container,
        stats: !!DOM.stats,
        pagination: !!DOM.pagination,
        loadMoreBtn: !!DOM.loadMoreBtn,
        noPhotosMessage: !!DOM.noPhotosMessage
    });
}

/**
 * Загружает список фотографий с сервера
 */
async function loadPhotos() {
    if (GalleryState.isLoading) {
        console.log('⏳ Загрузка уже выполняется...');
        return;
    }
    
    try {
        showLoading(true);
        GalleryState.isLoading = true;
        console.log('📡 Запрашиваю фото с сервера...');
        
        // Отправляем запрос к API
        const response = await fetch(API_ENDPOINTS.LIST);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Сохраняем данные в состояние
            GalleryState.allPhotos = data.photos || [];
            GalleryState.totalCount = data.count || 0;
            GalleryState.totalSize = data.total_size || '0 B';
            GalleryState.hasMore = GalleryState.allPhotos.length < GalleryState.totalCount;
            
            // Обновляем интерфейс
            updatePhotosStats(data);
            renderPhotos();
            toggleNoPhotosMessage();
            updatePaginationControls();
            
            // Логируем успешную загрузку
            console.log(`✅ Загружено ${GalleryState.allPhotos.length} фото из ${GalleryState.totalCount}`);
            
        } else {
            throw new Error(data.message || 'Неизвестная ошибка сервера');
        }
        
    } catch (error) {
        console.error('❌ Ошибка при загрузке фотографий:', error);
        showError(`Ошибка загрузки: ${error.message}`);
    } finally {
        showLoading(false);
        GalleryState.isLoading = false;
    }
}

/**
 * Показывает/скрывает индикатор загрузки
 */
function showLoading(isLoading) {
    if (!DOM.container) return;
    
    if (isLoading) {
        DOM.container.innerHTML = `
            <div class="loading-container">
                <div class="spinner"></div>
                <p>Загрузка фотографий...</p>
            </div>
        `;
        
        if (DOM.loadMoreBtn) {
            DOM.loadMoreBtn.disabled = true;
            DOM.loadMoreBtn.innerHTML = '<span class="spinner-small"></span> Загрузка...';
        }
    }
}

/**
 * Отображает статистику фотографий
 */
function updatePhotosStats(data) {
    if (!DOM.stats) return;
    
    const statsHTML = `
        <span class="stat-item" title="Всего файлов">
            📊 ${data.count || 0}
        </span>
        <span class="stat-item" title="Общий размер">
            💾 ${data.total_size || '0 B'}
        </span>
        <span class="stat-item" title="Показано">
            👁️ ${data.limited_count || 0}
        </span>
    `;
    
    DOM.stats.innerHTML = statsHTML;
}

/**
 * Переключает сообщение "Нет фотографий"
 */
function toggleNoPhotosMessage() {
    if (!DOM.noPhotosMessage || !DOM.container) return;
    
    const hasPhotos = GalleryState.allPhotos.length > 0;
    
    DOM.noPhotosMessage.style.display = hasPhotos ? 'none' : 'block';
    DOM.container.style.display = hasPhotos ? 'grid' : 'none';
    DOM.pagination.style.display = hasPhotos ? 'flex' : 'none';
}

/**
 * Обновляет элементы управления пагинацией
 */
function updatePaginationControls() {
    if (!DOM.loadMoreBtn) return;
    
    const shownCount = GalleryState.allPhotos.length;
    const totalCount = GalleryState.totalCount;
    
    // Обновляем текст кнопки "Загрузить еще"
    if (GalleryState.hasMore && shownCount < totalCount) {
        DOM.loadMoreBtn.style.display = 'block';
        DOM.loadMoreBtn.disabled = false;
        DOM.loadMoreBtn.innerHTML = `📥 Загрузить еще (${shownCount}/${totalCount})`;
    } else {
        DOM.loadMoreBtn.style.display = 'none';
    }
    
    // Обновляем счетчик
    const countElement = document.getElementById('photos-count');
    if (countElement) {
        countElement.textContent = `${shownCount} из ${totalCount} фото`;
    }
}

/**
 * Рендерит фотографии в галерею
 */
function renderPhotos() {
    if (!DOM.container) return;
    
    // Если фото нет, показываем сообщение
    if (GalleryState.allPhotos.length === 0) {
        DOM.container.innerHTML = `
            <div class="empty-gallery">
                <p>Фотографии не найдены</p>
            </div>
        `;
        return;
    }
    
    // Рассчитываем, какие фото показывать на текущей странице
    const startIndex = 0; // Показываем все загруженные
    const endIndex = GalleryState.currentPage * GalleryState.photosPerPage;
    const photosToShow = GalleryState.allPhotos.slice(startIndex, endIndex);
    
    // Создаем HTML для каждой фотографии
    const photosHTML = photosToShow.map(photo => createPhotoCard(photo)).join('');
    
    DOM.container.innerHTML = `
        <div class="photos-grid">
            ${photosHTML}
        </div>
    `;
    
    // Добавляем обработчики событий для карточек
    attachPhotoEventListeners();
}

/**
 * Создает HTML карточки для фотографии
 */
function createPhotoCard(photo) {
    const createdAt = formatDateTime(photo.created);
    const size = photo.size_formatted || formatFileSize(photo.size_bytes);
    
    return `
        <div class="photo-card" data-filename="${photo.filename}">
            <div class="photo-card-header">
                <span class="photo-name">${escapeHtml(photo.filename)}</span>
                <button class="btn-delete-photo" title="Удалить" onclick="confirmDeletePhoto('${photo.filename}')">
                    🗑️
                </button>
            </div>
            
            <div class="photo-preview" onclick="openPhotoViewer('${photo.url}', '${photo.filename}')">
                <img 
                    src="${photo.url}" 
                    alt="${photo.filename}"
                    loading="lazy"
                    onerror="this.src='/static/img/image-error.png'"
                >
                <div class="photo-overlay">
                    <span class="view-icon">👁️</span>
                </div>
            </div>
            
            <div class="photo-info">
                <div class="info-row">
                    <span class="info-label">Размер:</span>
                    <span class="info-value">${photo.resolution || 'N/A'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Вес:</span>
                    <span class="info-value">${size}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Создано:</span>
                    <span class="info-value">${createdAt}</span>
                </div>
                <div class="info-actions">
                    <button class="btn-action" onclick="downloadPhoto('${photo.url}', '${photo.filename}')" title="Скачать">
                        📥
                    </button>
                    <button class="btn-action" onclick="copyPhotoLink('${photo.url}')" title="Копировать ссылку">
                        🔗
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
 * Форматирует дату и время
 */
function formatDateTime(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleString('ru-RU', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return dateString || 'Неизвестно';
    }
}

/**
 * Форматирует размер файла
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    if (!bytes) return 'N/A';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Экранирует HTML символы для безопасности
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Показывает сообщение об ошибке
 */
function showError(message) {
    // Создаем или находим контейнер для ошибок
    let errorContainer = document.getElementById('error-container');
    
    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.id = 'error-container';
        errorContainer.className = 'error-container';
        document.querySelector('.photos-preview-section').prepend(errorContainer);
    }
    
    errorContainer.innerHTML = `
        <div class="alert alert-error">
            <span>❌ ${escapeHtml(message)}</span>
            <button class="btn-close" onclick="this.parentElement.remove()">×</button>
        </div>
    `;
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        if (errorContainer && errorContainer.firstChild) {
            errorContainer.firstChild.remove();
        }
    }, 5000);
}

/**
 * Добавляет обработчики событий для карточек фото
 */
function attachPhotoEventListeners() {
    // Добавляем обработчики для превью
    document.querySelectorAll('.photo-preview').forEach(preview => {
        preview.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.02)';
        });
        
        preview.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });
}

/**
 * Подтверждение удаления фотографии
 */
function confirmDeletePhoto(filename) {
    if (!confirm(`Удалить фотографию "${filename}"?`)) {
        return;
    }
    
    deletePhoto(filename);
}

/**
 * Удаляет фотографию
 */
async function deletePhoto(filename) {
    try {
        console.log(`🗑️ Удаляю фото: ${filename}`);
        
        const response = await fetch(`${API_ENDPOINTS.DELETE}/${filename}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification(`✅ Фото "${filename}" удалено`, 'success');
            // Перезагружаем список
            loadPhotos();
        } else {
            throw new Error(data.message);
        }
        
    } catch (error) {
        console.error('❌ Ошибка удаления:', error);
        showNotification(`❌ Ошибка удаления: ${error.message}`, 'error');
    }
}

/**
 * Очищает все фотографии
 */
async function clearAllPhotos() {
    if (!confirm('Вы уверены, что хотите удалить ВСЕ фотографии? Это действие нельзя отменить.')) {
        return;
    }
    
    try {
        console.log('🗑️ Очищаю все фото...');
        
        const response = await fetch(API_ENDPOINTS.CLEAR, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification(`✅ Удалено ${data.deleted_count} фото (${data.deleted_size_formatted})`, 'success');
            // Перезагружаем список
            loadPhotos();
        } else {
            throw new Error(data.message);
        }
        
    } catch (error) {
        console.error('❌ Ошибка очистки:', error);
        showNotification(`❌ Ошибка очистки: ${error.message}`, 'error');
    }
}

/**
 * Загружает больше фотографий (пагинация)
 */
function loadMorePhotos() {
    if (GalleryState.isLoading || !GalleryState.hasMore) return;
    
    GalleryState.currentPage++;
    renderPhotos();
    updatePaginationControls();
}

/**
 * Открывает просмотрщик фотографий
 */
function openPhotoViewer(url, filename) {
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.className = 'photo-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closePhotoViewer()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>${escapeHtml(filename)}</h3>
                <button class="modal-close" onclick="closePhotoViewer()">×</button>
            </div>
            <div class="modal-body">
                <img src="${url}" alt="${filename}">
            </div>
            <div class="modal-footer">
                <button class="btn btn-info" onclick="downloadPhoto('${url}', '${filename}')">
                    📥 Скачать
                </button>
                <button class="btn btn-secondary" onclick="closePhotoViewer()">
                    Закрыть
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden'; // Блокируем скролл
}

/**
 * Закрывает просмотрщик фотографий
 */
function closePhotoViewer() {
    const modal = document.querySelector('.photo-modal');
    if (modal) {
        modal.remove();
    }
    document.body.style.overflow = ''; // Восстанавливаем скролл
}

/**
 * Скачивает фотографию
 */
function downloadPhoto(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showNotification(`✅ Фото "${filename}" скачивается...`, 'success');
}

/**
 * Копирует ссылку на фотографию
 */
function copyPhotoLink(url) {
    navigator.clipboard.writeText(window.location.origin + url)
        .then(() => {
            showNotification('✅ Ссылка скопирована в буфер обмена', 'success');
        })
        .catch(err => {
            console.error('❌ Ошибка копирования:', err);
            showNotification('❌ Не удалось скопировать ссылку', 'error');
        });
}

/**
 * Показывает уведомление
 */
function showNotification(message, type = 'info') {
    // Удаляем старое уведомление, если есть
    const oldNotification = document.getElementById('custom-notification');
    if (oldNotification) {
        oldNotification.remove();
    }
    
    // Создаем новое уведомление
    const notification = document.createElement('div');
    notification.id = 'custom-notification';
    notification.innerHTML = `
        <div style="
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? '#e53e3e' : '#48bb78'};
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            max-width: 300px;
            animation: slideIn 0.3s ease;
        ">
            <div style="font-weight: bold; margin-bottom: 5px;">
                ${type === 'error' ? '❌ Ошибка' : '✅ Успех'}
            </div>
            <div>${message}</div>
        </div>
    `;
    
    // Добавляем стили для анимации
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(notification);
    
    // Автоматически скрываем через 5 секунд
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease forwards';
            
            const slideOutStyle = document.createElement('style');
            slideOutStyle.textContent = `
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(slideOutStyle);
            
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
                if (slideOutStyle.parentNode) {
                    slideOutStyle.remove();
                }
            }, 300);
        }
    }, 5000);
}

// Экспортируем функции в глобальную область видимости
window.loadPhotos = loadPhotos;
window.clearAllPhotos = clearAllPhotos;
window.loadMorePhotos = loadMorePhotos;
window.confirmDeletePhoto = confirmDeletePhoto;
window.deletePhoto = deletePhoto;
window.openPhotoViewer = openPhotoViewer;
window.closePhotoViewer = closePhotoViewer;
window.downloadPhoto = downloadPhoto;
window.copyPhotoLink = copyPhotoLink;