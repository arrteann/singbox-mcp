"""MCP server exposing sing-box documentation search."""

from __future__ import annotations

import json
import os
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from .rag import DEFAULT_TOP_K, RAGSystem

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
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 - surface tool errors to the MCP client
        return json.dumps(
            {
                "error": True,
                "message": str(exc),
            },
            indent=2,
        )


def main() -> None:
    if "PORT" in os.environ:
        print(f"🚀 Starting MCP Server on port {port} (HTTP SSE mode)...")
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
