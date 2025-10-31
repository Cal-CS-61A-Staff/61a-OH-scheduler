from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from . import paths


def configure_logging(log_level: int = logging.INFO) -> None:
    """Configure the root logger with a rotating file handler."""
    paths.ensure_directories()

    log_file = paths.LOG_DIR / f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Avoid adding duplicate handlers if configure_logging is called twice.
        return

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info("Logging initialised. Writing to %s", log_file)

