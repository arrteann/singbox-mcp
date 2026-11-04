"""CLI entrypoint: python -m singbox_mcp <command>."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="singbox-mcp",
        description="Scrape, index, and serve sing-box documentation via MCP.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scrape", help="Crawl sing-box docs into data.json")
    sub.add_parser("build-index", help="Chunk docs and build the FAISS + BM25 index")
    sub.add_parser("serve", help="Start the MCP server (stdio, or SSE if PORT is set)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scrape":
        from .scraper import main as scrape_main

        scrape_main()
        return 0

    if args.command == "build-index":
        from .rag import main as rag_main

        rag_main()
        return 0

    if args.command == "serve":
        from .server import main as serve_main

        serve_main()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
