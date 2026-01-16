"""
Structured Logging Configuration for InsightWeaver

Provides:
- JSON formatting for production
- Log rotation with size limits
- Contextual logging with structured data
- Multiple output handlers (file, console, JSON)
"""

import json
import logging
import logging.handlers
import sys
from typing import Any

from src.config.settings import settings


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    Outputs log records as JSON for easy parsing and analysis
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class StructuredLogger(logging.LoggerAdapter):
    """
    Logger adapter for adding contextual information to logs

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing item", extra_fields={"item_id": 123, "status": "active"})
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Add extra_fields to the log record"""
        extra_fields = kwargs.pop("extra_fields", {})
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        kwargs["extra"]["extra_fields"] = extra_fields
        return msg, kwargs


def setup_logging(json_output: bool = False) -> logging.Logger:
    """
    Configure application logging with rotation and structured output

    Args:
        json_output: If True, use JSON formatting for file output

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    settings.logs_dir.mkdir(exist_ok=True, parents=True)

    # Remove existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set root logger level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # Rotating file handler (prevents log files from growing too large)
    log_file = settings.logs_dir / "insightweaver.log"
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backup files
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)

    # Use JSON formatter for file if requested
    if json_output:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(console_format)

    root_logger.addHandler(file_handler)

    # JSON-only log file (always JSON format for easy parsing)
    json_log_file = settings.logs_dir / "insightweaver.json.log"
    json_handler = logging.handlers.RotatingFileHandler(
        filename=json_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    json_handler.setLevel(log_level)
    json_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(json_handler)

    # Set specific log levels for third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured successfully", extra={"extra_fields": {"json_output": json_output}}
    )

    return logger


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance with contextual logging support

    Example:
        logger = get_logger(__name__)
        logger.info("User action", extra_fields={"user_id": 123, "action": "login"})
    """
    base_logger = logging.getLogger(name)
    return StructuredLogger(base_logger, {})


def log_execution_time(func):
    """
    Decorator to log function execution time

    Usage:
        @log_execution_time
        async def my_function():
            ...
    """
    import functools
    import time

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(
                f"{func.__name__} completed",
                extra_fields={"duration_seconds": elapsed, "function": func.__name__},
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"{func.__name__} failed",
                extra_fields={
                    "duration_seconds": elapsed,
                    "function": func.__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(
                f"{func.__name__} completed",
                extra_fields={"duration_seconds": elapsed, "function": func.__name__},
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"{func.__name__} failed",
                extra_fields={
                    "duration_seconds": elapsed,
                    "function": func.__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    # Return appropriate wrapper based on whether function is async
    import asyncio

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
