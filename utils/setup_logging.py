import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# DEBUG /  INFO / WARNING / ERROR / CRITICAL
logging_mode = logging.INFO


def setup_logging(log_file: str = None):
    if not log_file:
        log_file = "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging_mode)

    # Avoid duplicate handlers if setup_logging() is accidentally called twice
    if root_logger.handlers:
        return log_file

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s"
        # "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=512 * 1024,  # 500KB
        backupCount=1,  # Keep 1 log file only
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Capture uncaught Python exceptions
    def exception_hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(
                exc_type,
                exc_value,
                exc_traceback,
            )
            return

        logging.getLogger("uncaught").critical(
            "Uncaught exception",
            exc_info=(
                exc_type,
                exc_value,
                exc_traceback,
            ),
        )

    sys.excepthook = exception_hook

    return log_file


def set_log_level(level: str):
    level = getattr(logging, level.upper(), logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers:
        handler.setLevel(level)
