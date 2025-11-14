"""Logging configuration and utilities"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Global log file paths
TRADE_LOG_FILE: Optional[str] = None
ERROR_LOG_FILE: Optional[str] = None
MAIN_LOG_FILE: Optional[str] = None


def setup_logger(
    name: str = "PolyHFT", 
    log_level: str = "INFO", 
    log_file: str = None,
    console: bool = True
) -> logging.Logger:
    """
    Set up a logger with console and/or file handlers.
    
    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        console: Whether to output to console (default: True)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (if enabled)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def setup_multi_logger(
    main_log_file: str = "logs/bot.log",
    trade_log_file: str = "logs/trades.log",
    error_log_file: str = "logs/errors.log",
    log_level: str = "INFO"
):
    """
    Set up multiple loggers for different purposes.
    
    Args:
        main_log_file: Path to main log file (all logs)
        trade_log_file: Path to trade log file (trades only)
        error_log_file: Path to error log file (errors/warnings only)
        log_level: Logging level
    """
    global TRADE_LOG_FILE, ERROR_LOG_FILE, MAIN_LOG_FILE
    
    TRADE_LOG_FILE = trade_log_file
    ERROR_LOG_FILE = error_log_file
    MAIN_LOG_FILE = main_log_file
    
    # Create log directories
    for log_file in [main_log_file, trade_log_file, error_log_file]:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Setup main logger (file only, no console)
    main_logger = logging.getLogger("PolyHFT")
    main_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    main_logger.handlers.clear()
    
    # Main log file handler (everything)
    main_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    main_file_handler = logging.FileHandler(main_log_file)
    main_file_handler.setLevel(logging.DEBUG)
    main_file_handler.setFormatter(main_formatter)
    main_logger.addHandler(main_file_handler)
    
    # Setup trade logger (console + trade file)
    trade_logger = logging.getLogger("PolyHFT.Trades")
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers.clear()
    trade_logger.propagate = False  # Don't propagate to parent
    
    # Console handler for trades
    trade_console_handler = logging.StreamHandler(sys.stdout)
    trade_console_handler.setLevel(logging.INFO)
    trade_formatter = logging.Formatter('%(message)s')  # Simple format for trades
    trade_console_handler.setFormatter(trade_formatter)
    trade_logger.addHandler(trade_console_handler)
    
    # Trade log file handler
    trade_file_handler = logging.FileHandler(trade_log_file)
    trade_file_handler.setLevel(logging.INFO)
    trade_file_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    trade_file_handler.setFormatter(trade_file_formatter)
    trade_logger.addHandler(trade_file_handler)
    
    # Setup error logger (error file only, no console)
    error_logger = logging.getLogger("PolyHFT.Errors")
    error_logger.setLevel(logging.WARNING)
    error_logger.handlers.clear()
    error_logger.propagate = False  # Don't propagate to parent
    
    # Error log file handler
    error_file_handler = logging.FileHandler(error_log_file)
    error_file_handler.setLevel(logging.WARNING)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_file_handler.setFormatter(error_formatter)
    error_logger.addHandler(error_file_handler)
    
    # Also add error handler to main logger to catch all errors
    error_handler = logging.FileHandler(error_log_file)
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(error_formatter)
    main_logger.addHandler(error_handler)


def get_trade_logger() -> logging.Logger:
    """Get the trade logger (console + trade file)"""
    logger = logging.getLogger("PolyHFT.Trades")
    # If logger hasn't been set up yet, return a null logger that won't crash
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def get_error_logger() -> logging.Logger:
    """Get the error logger (error file only)"""
    logger = logging.getLogger("PolyHFT.Errors")
    # If logger hasn't been set up yet, return a null logger that won't crash
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger

