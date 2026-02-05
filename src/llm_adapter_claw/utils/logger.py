"""Logging configuration with structlog."""

import sys

import structlog


def configure_logging(log_level: str = "info") -> None:
    """Configure structured logging.
    
    Args:
        log_level: Logging level (debug, info, warning, error)
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if sys.stderr.isatty() else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    """Get a structured logger.
    
    Args:
        name: Logger name, defaults to caller module
        
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
