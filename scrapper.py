#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer: python -m singbox_mcp scrape"""

from singbox_mcp.scraper import main

if __name__ == "__main__":
    main()
