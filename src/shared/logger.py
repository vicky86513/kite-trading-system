"""
Shared logger — every script logs into ONE common file per day.

All log lines go to: Logs/trading_logs_.txt
Plus console output.
"""

import os
import logging
from datetime import date

from . import config

LOG_DIR = config.LOG_DIR

_configured_names = set()


def _dated_log_path():
    return LOG_DIR / f"trading_logs_{date.today()}.txt"


class DailyFileHandler(logging.Handler):
    """Minimal daily-rotating file handler.
    
    Writes to Logs/trading_logs_.txt and automatically switches to a
    fresh, freshly-dated file the instant the calendar date changes.
    """

    def __init__(self, formatter):
        super().__init__()
        self.setFormatter(formatter)
        self._current_date = None
        self._stream = None
        self._open_for_today()

    def _open_for_today(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if self._stream:
            self._stream.close()
        self._current_date = date.today()
        self._stream = open(_dated_log_path(), "a", encoding="utf-8")

    def emit(self, record):
        if date.today() != self._current_date:
            self._open_for_today()
        try:
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def __del__(self):
        """Cleanup on garbage collection."""
        if self._stream:
            self._stream.close()

    def close(self):
        """Allow explicit cleanup."""
        if self._stream:
            self._stream.close()
        super().close()


def get_logger(name):
    """Returns a logger tagged with `name` (e.g. 'MCX', 'NIFTY', 'AUTH').
    
    All loggers write to the same day's Logs/trading_logs_.txt file,
    plus the console.
    """
    logger = logging.getLogger(name)

    if name in _configured_names:
        return logger  # already configured — avoid duplicate handlers

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
    )

    # File handler
    file_handler = DailyFileHandler(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _configured_names.add(name)
    return logger