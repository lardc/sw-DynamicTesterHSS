import logging
import os
from logging.handlers import RotatingFileHandler


LOG_FORMAT = '%(asctime)s, %(levelname)s, %(name)s, %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(log_file_path: str):
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    root_logger.info("Logger initialized")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

