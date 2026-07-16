"""Structured logging setup.

Configures `structlog` on top of the standard library `logging` module so
that third-party libraries (uvicorn, sqlalchemy, ultralytics) and
SENTINEL Detect's own code emit through the same pipeline. `configure_logging`
must be called once at process startup, before any logger is used.
"""

from __future__ import annotations

import logging
import sys

import structlog

from sentinel_detect.config.settings import LoggingSettings


def configure_logging(settings: LoggingSettings) -> None:
    """Configure stdlib logging + structlog for the current process."""
    level = getattr(logging, settings.level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.json_format
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger, conventionally called with `__name__`."""
    logger: structlog.BoundLogger = structlog.get_logger(name)
    return logger
