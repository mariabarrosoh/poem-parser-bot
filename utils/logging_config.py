# utils/logging_config.py
import logging
import sys

def configure_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Configure and return a logger with standardized format and console output.

    Args:
        name (str): The name of the logger to configure.
        level (int): Logging level (default: logging.INFO).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger
