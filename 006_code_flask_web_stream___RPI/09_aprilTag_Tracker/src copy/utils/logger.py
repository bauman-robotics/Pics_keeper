"""
Настройка логирования
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(config):
    """
    Настройка логгера
    
    Args:
        config: конфигурация логирования
    """
    level = getattr(logging, config.get('level', 'INFO'))
    log_file = config.get('file', 'logs/aprilTag_tracker.log')
    console = config.get('console', True)
    
    # Создание директории для логов
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Создание логгера
    logger = logging.getLogger('AprilTagTracker')
    logger.setLevel(level)
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Файловый обработчик
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный обработчик
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger
