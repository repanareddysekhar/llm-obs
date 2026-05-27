"""
SDK-internal logger.
All llm_obs components use get_logger(__name__) so the application
can configure the "llm_obs" logger hierarchy as needed.
"""
from __future__ import annotations

import logging


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"llm_obs.{name}" if name else "llm_obs")


# Null handler so the SDK never emits output unless the host app configures logging.
logging.getLogger("llm_obs").addHandler(logging.NullHandler())
