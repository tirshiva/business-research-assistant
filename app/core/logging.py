"""Centralized logging configuration for the application."""

from __future__ import annotations

import logging
import sys
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
DEFAULT_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logging used by all application modules.

    Ensures every log record includes:
    - timestamp
    - log level
    - module / logger name
    - message
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers when setup_logging is called more than once
    # (e.g. in tests or under multiple workers).
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(fmt=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
    )
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for use by application modules.

    Prefer calling this with ``__name__`` so log records identify the module.
    """
    return logging.getLogger(name)
