"""Centralized logging configuration for Automated Desktop File Organizer."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str="file_organizer",
    log_file: Optional[Path]=None,
    level: int=logging.INFO,
) -> logging.Logger:
    """Set up and return a logger with both console and file handlers.

    Args:
        name: Logger name.
        log_file: Path to log file. Defaults to `logs/organizer.log`.
        level: Logging level (e.g. logging.INFO, logging.DEBUG).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler with safe Windows encoding handling
    try:
        if sys.platform == "win32":
            reconfigure = getattr(sys.stdout, "reconfigure", None)
            if callable(reconfigure):
                reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_file is None:
        log_file = Path("logs") / "organizer.log"

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file log handler at {log_file}: {e}")

    return logger
