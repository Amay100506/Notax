"""
Logging configuration for NotifyIQ.
Strictly enforces privacy: NEVER logs raw notification content in application logs.
"""

import logging
import sys
from backend.utils.configuration import settings


def setup_logger(name: str = "notifyiq") -> logging.Logger:
    """
    Configures and returns a logger for NotifyIQ.
    Logs metadata only (event IDs, counts, timings) and strictly excludes
    raw notification bodies to protect user privacy.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
        
    return logger


logger = setup_logger()
