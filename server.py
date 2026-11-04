#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer: python -m singbox_mcp serve"""

from singbox_mcp.server import main

if __name__ == "__main__":
    main()
