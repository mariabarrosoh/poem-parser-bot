"""
Logging Configuration Utility

Provides a helper function to create a standardized logger with
console output and consistent formatting across the project.
"""

import logging
import sys
from typing import Optional


def configure_logger(
    name: str,
    level: int = logging.INFO,
    fmt: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt: Optional[str] = "%Y-%m-%d %H:%M:%S",
    stream=sys.stdout
) -> logging.Logger:
    """
    Configure and return a logger with standardized format and console output.

    Args:
        name (str): Name of the logger to configure.
        level (int, optional): Logging level (default: logging.INFO).
        fmt (str, optional): Format string for log messages.
        datefmt (str, optional): Date/time format for log messages.
        stream (IO, optional): Output stream (default: sys.stdout).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger is reconfigured
    if not logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger
