#!/usr/bin/env python3
"""
Парсер аргументов командной строки для Pics_keeper
"""

import argparse
from typing import Optional
from .settings import ApplicationSettings


class CLIParser:
    """Парсер аргументов командной строки"""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Создание парсера с группами аргументов"""
        parser = argparse.ArgumentParser(
            description='Калибровка камер Raspberry Pi с отдельными настройками стрима',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Примеры использования:
  %(prog)s                                           # IMX708, стрим 1280x720 без анализа
  %(prog)s --camera imx708 --stream-width 640 --stream-height 480
  %(prog)s --no-analysis --stream-fps 60             # Макс. FPS, без анализа
  %(prog)s --no-stream                               # Без стрима
  %(prog)s --stream-width 1920 --stream-height 1080  # Full HD стрим
"""
        )
        
        # Группа параметров камеры
        camera_group = parser.add_argument_group('Параметры камеры')
        camera_group.add_argument('--camera', type=str, default='local_web',
                                 choices=['imx708', 'imx415', 'ov5647', 'local_web'],
                                 help='Тип камеры (по умолчанию: local_web)')
        camera_group.add_argument('--resolution', type=str, default='full',
                                 choices=['full', 'stream'],
                                 help='Разрешение съемки: full=полное, stream=стримовое (по умолчанию: full)')
        
        # Группа параметров стрима
        stream_group = parser.add_argument_group('Параметры стрима')
        stream_group.add_argument('--stream-width', type=int, default=1280,
                                 help='Ширина стрима (по умолчанию: 1280)')
        stream_group.add_argument('--stream-height', type=int, default=720,
                                 help='Высота стрима (по умолчанию: 720)')
        stream_group.add_argument('--stream', action='store_true', default=True,
                                 help='Включить стрим (по умолчанию: ВКЛЮЧЕН)')
        stream_group.add_argument('--no-stream', action='store_false', dest='stream',
                                 help='Выключить стрим')
        stream_group.add_argument('--stream-fps', type=int, default=30,
                                 help='Частота кадров стрима (по умолчанию: 30)')
        stream_group.add_argument('--stream-quality', type=int, default=50,
                                 help='Качество JPEG стрима 1-100 (по умолчанию: 50)')
        stream_group.add_argument('--stream-analysis', action='store_true', default=False,
                                 help='Включить анализ шахматной доски в стриме')
        stream_group.add_argument('--no-analysis', action='store_false', dest='stream_analysis',
                                 help='Отключить анализ в стриме (рекомендуется)')
        stream_group.add_argument('--low-latency', action='store_true', default=True,
                                 help='Режим низкой задержки (по умолчанию: ВКЛЮЧЕН)')
        stream_group.add_argument('--stream-port', type=int, default=8080,
                                 help='Порт стрима (по умолчанию: 8080)')
        
        # Группа параметров съемки
        capture_group = parser.add_argument_group('Параметры съемки')
        capture_group.add_argument('--delay', type=float, default=0,
                                  help='Задержка перед снимком в секундах (по умолчанию: 0)')
        capture_group.add_argument('--count', type=int, default=20,
                                  help='Количество изображений (по умолчанию: 20)')
        capture_group.add_argument('--output-dir', type=str, default='003_pics',
                                  help='Выходная директория (по умолчанию: "003_pics")')
        capture_group.add_argument('--jpeg-quality', type=int, default=95,
                                  help='Качество JPEG снимков 1-100 (по умолчанию: 95)')
        
        # Группа параметров контроля углов
        angle_group = parser.add_argument_group('Контроль углов наклона')
        angle_group.add_argument('--max-angle', type=float, default=45,
                                help='Максимальный допустимый угол наклона (градусы) (по умолчанию: 45)')
        angle_group.add_argument('--warn-angle', type=float, default=30,
                                help='Угол для предупреждения (градусы) (по умолчанию: 30)')
        angle_group.add_argument('--force-capture', action='store_true',
                                help='Делать снимки даже при большом угле наклона')
        
        # Группа параметров отображения
        display_group = parser.add_argument_group('Параметры отображения')
        display_group.add_argument('--preview', action='store_true', default=False,
                                  help='Показывать окно предпросмотра')
        
        # Группа параметров отладки
        debug_group = parser.add_argument_group('Параметры отладки')
        debug_group.add_argument('--debug', action='store_true', help='Включить вывод отладки')
        
        # Группа параметров экспозиции и фокусировки
        expofocus_group = parser.add_argument_group('Параметры экспозиции и фокусировки')
        expofocus_group.add_argument('--exposure-time', type=int, default=40000,
                                   help='Выдержка в микросекундах (по умолчанию: 40000)')
        expofocus_group.add_argument('--analogue-gain', type=float, default=2.0,
                                   help='Аналоговое усиление (по умолчанию: 2.0)')
        expofocus_group.add_argument('--ae-enable', action='store_true', default=False,
                                   help='Включить автоэкспозицию (по умолчанию: ВЫКЛ)')
        expofocus_group.add_argument('--no-ae', action='store_false', dest='ae_enable',
                                   help='Выключить автоэкспозицию')
        expofocus_group.add_argument('--af-enable', action='store_true', default=False,
                                   help='Включить автофокус (по умолчанию: ВЫКЛ)')
        expofocus_group.add_argument('--no-af', action='store_false', dest='af_enable',
                                   help='Выключить автофокус')
        expofocus_group.add_argument('--lens-position', type=float, default=0.5,
                                   help='Позиция линзы (по умолчанию: 0.5)')
        
        return parser
    
    def parse_args(self) -> ApplicationSettings:
        """Парсинг аргументов и создание настроек"""
        args = self.parser.parse_args()
        return ApplicationSettings.from_args(args)
    
    def parse_args_raw(self):
        """Парсинг аргументов без создания настроек"""
        return self.parser.parse_args()
    
    def print_help(self):
        """Вывод справки"""
        self.parser.print_help()
    
    def get_parser(self) -> argparse.ArgumentParser:
        """Получение парсера для внешнего использования"""
        return self.parser


def create_cli_parser() -> CLIParser:
    """Создание экземпляра парсера"""
    return CLIParser()


def parse_arguments() -> ApplicationSettings:
    """Парсинг аргументов командной строки"""
    parser = create_cli_parser()
    return parser.parse_args()