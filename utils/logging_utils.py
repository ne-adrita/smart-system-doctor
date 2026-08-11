"""Logging utilities: file + console logger with rotating file handler."""
import logging
import os
from logging.handlers import RotatingFileHandler

from config import Config

_configured = False


def setup_logger(name: str = "smart-system-doctor") -> logging.Logger:
    """Return a configured logger. Safe to call multiple times."""
    global _configured
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    os.makedirs(Config.LOG_DIR, exist_ok=True)
    log_file = os.path.join(Config.LOG_DIR, Config.LOG_FILE)

    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    if os.environ.get("SSD_LOG_CONSOLE", "0") == "1":
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    _configured = True
    return logger


def get_logger(name: str = "smart-system-doctor") -> logging.Logger:
    return setup_logger(name)
