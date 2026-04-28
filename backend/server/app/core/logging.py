"""
FarmShield Backend — Structured Logging Setup.

Configures structlog with JSON output in prod and pretty-print in dev.
Called once in main.py lifespan before anything else logs.
All application code uses `structlog.get_logger(__name__)`.
"""

import logging
import sys

import structlog


def configure_logging(log_level: str, log_json: bool) -> None:
    """
    Set up structlog and bridge stdlib logging.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR.
        log_json: True for machine-readable JSON (prod/Pi),
                  False for human-readable coloured output (dev).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Shared processors applied to every log event
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_json:
        # Production: JSON lines to stdout
        renderer = structlog.processors.JSONRenderer()
    else:
        # Dev: coloured, human-readable console output
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to route through structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Silence noisy third-party loggers
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "asyncio"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
