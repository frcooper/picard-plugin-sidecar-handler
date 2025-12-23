from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger.

    When running inside Picard, Picard may configure logging handlers.
    During tests, this falls back to standard Python logging.
    """

    logger = logging.getLogger(name)
    if not logger.handlers:
        # Avoid "No handler" warnings in unit tests.
        logging.basicConfig(level=logging.INFO)
    return logger
