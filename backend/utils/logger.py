"""
Logging configuration for NeoLab SmartStock.
"""
import logging
import sys
from typing import Optional

# Default logging format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configure root logger
def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None
):
    """Configure root logging."""
    formatter = logging.Formatter(format_string or DEFAULT_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from external libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


# Configure on import
configure_logging()
