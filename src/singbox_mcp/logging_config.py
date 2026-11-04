"""Shared logging setup for CLI and server processes."""

from __future__ import annotations

import logging
import os


def setup_logging(level: str | None = None) -> None:
    resolved = (level or os.environ.get("SINGBOX_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
