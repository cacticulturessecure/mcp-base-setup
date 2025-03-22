#!/usr/bin/env python3
"""
Logging utilities for SimpleAnthropicCLI
"""

import os
import logging
from typing import Optional
import datetime

# Log file path
CONFIG_DIR = os.path.expanduser("~/.simple_anthropic_cli")
LOGS_DIR = os.path.join(CONFIG_DIR, "logs")
LOG_FILE = os.path.join(LOGS_DIR, "cli.log")

def setup_logging(log_level: int = logging.INFO, console_output: bool = False) -> None:
    """Configure logging for the application.
    
    Args:
        log_level: Logging level (default: INFO)
        console_output: Whether to output logs to console (default: False)
    """
    # Ensure logs directory exists
    if not os.path.exists(LOGS_DIR):
        try:
            os.makedirs(LOGS_DIR)
        except Exception as e:
            print(f"Error creating logs directory: {e}")
            # Fall back to using the main config dir
            global LOG_FILE
            LOG_FILE = os.path.join(CONFIG_DIR, "cli.log")
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates on reconfiguration
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Define log format
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    try:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file logging: {e}")
    
    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)
    
    logging.info(f"Logging initialized at {datetime.datetime.now().isoformat()}")

def get_logger(name: str) -> logging.Logger:
    """Get a named logger.
    
    Args:
        name: Name for the logger (typically module name)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

def log_exception(e: Exception, message: Optional[str] = None) -> None:
    """Log an exception with an optional message.
    
    Args:
        e: The exception to log
        message: Optional message to include
    """
    if message:
        logging.exception(f"{message}: {str(e)}")
    else:
        logging.exception(str(e))