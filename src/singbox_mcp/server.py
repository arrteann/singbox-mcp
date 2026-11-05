"""MCP server exposing sing-box documentation search."""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from .rag import DEFAULT_TOP_K, RAGSystem

logger = logging.getLogger(__name__)

rag_system = RAGSystem()

port = int(os.environ.get("PORT", "8000"))
mcp = FastMCP("singbox_docs_mcp", host="0.0.0.0", port=port)


class SearchQueryInput(BaseModel):
    """Input model for searching the RAG index."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ...,
        description="The search query to look up in the sing-box documentation.",
        min_length=2,
        max_length=200,
    )
    top_k: int = Field(
        DEFAULT_TOP_K,
        ge=1,
        le=20,
        description="Number of chunks to return.",
    )
    mode: Literal["hybrid", "semantic", "keyword"] = Field(
        "hybrid",
        description=(
            "Retrieval mode: hybrid (BM25 + semantic RRF), semantic (FAISS only), "
            "or keyword (BM25 only)."
        ),
    )


@mcp.tool(
    name="search_docs",
    annotations={
        "title": "Search sing-box Documentation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def search_docs(params: SearchQueryInput) -> str:
    """Search the sing-box documentation using hybrid RAG retrieval.

    Returns JSON with matched chunks, fused relevance scores, and section metadata
    (url, title, heading_path). Prefer mode=hybrid for config lookups.
    """
    try:
        results = rag_system.search(params.query, top_k=params.top_k, mode=params.mode)
        return json.dumps(
            {
                "error": False,
                "query": params.query,
                "mode": params.mode,
                "count": len(results),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    except FileNotFoundError as exc:
        logger.exception("Index missing during search")
        return json.dumps(
            {
                "error": True,
                "code": "index_not_found",
                "message": str(exc),
                "hint": "Run: python -m singbox_mcp build-index",
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001 - surface tool errors to the MCP client
        logger.exception("Search failed for query=%r", params.query)
        return json.dumps(
            {
                "error": True,
                "code": "search_failed",
                "message": str(exc),
            },
            indent=2,
        )


def main() -> None:
    if "PORT" in os.environ:
        logger.info("Starting MCP server on 0.0.0.0:%s (SSE)", port)
        mcp.run(transport="sse")
    else:
        logger.info("Starting MCP server (stdio)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    from .logging_config import setup_logging

    setup_logging()
    main()
