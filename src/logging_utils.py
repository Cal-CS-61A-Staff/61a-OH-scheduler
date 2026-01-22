from __future__ import annotations

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from . import paths


LOG_LEVEL_ENV_VAR = "OH_SCHEDULER_LOG_LEVEL"


def _resolve_log_level(default: int) -> int:
    """Return log level from env or fall back to the provided default."""
    raw_level = os.environ.get(LOG_LEVEL_ENV_VAR)
    if not raw_level:
        return default

    if raw_level.isdigit():
        return int(raw_level)

    mapped_level = getattr(logging, raw_level.upper(), None)
    if isinstance(mapped_level, int):
        return mapped_level

    logging.getLogger(__name__).warning(
        "Unknown %s value '%s'; defaulting to %s",
        LOG_LEVEL_ENV_VAR,
        raw_level,
        logging.getLevelName(default),
    )
    return default


def configure_logging(log_level: int = logging.INFO) -> None:
    """Configure the root logger with a rotating file handler."""
    paths.ensure_directories()

    log_file = paths.LOG_DIR / f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    resolved_level = _resolve_log_level(log_level)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(resolved_level)

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

    logging.getLogger(__name__).info(
        "Logging initialised at %s level (console fixed at WARNING). Writing to %s",
        logging.getLevelName(resolved_level),
        log_file,
    )
