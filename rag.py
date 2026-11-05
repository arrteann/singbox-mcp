#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer: python -m singbox_mcp build-index"""

from singbox_mcp.logging_config import setup_logging
from singbox_mcp.rag import main

if __name__ == "__main__":
    setup_logging()
    main()
