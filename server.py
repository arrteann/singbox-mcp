#!/usr/bin/env python3
import json
import os
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict
from rag import RAGSystem

# Initialize the RAG System (it will lazily load the FAISS index on the first search)
rag_system = RAGSystem()

# Get port from Railway environment (default to 8000 locally)
port = int(os.environ.get("PORT", 8000))

# Initialize the MCP server on 0.0.0.0 to support external deployment
mcp = FastMCP("singbox_docs_mcp", host="0.0.0.0", port=port)

class SearchQueryInput(BaseModel):
    '''Input model for searching the RAG index.'''
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    query: str = Field(..., description="The search query to look up in the sing-box documentation.", min_length=2, max_length=200)

@mcp.tool(
    name="search_docs",
    annotations={
        "title": "Search sing-box Documentation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def search_docs(params: SearchQueryInput) -> str:
    '''Search the sing-box documentation using RAG semantic search.
    
    This tool allows you to query the scraped sing-box documentation and get the most relevant
    content chunks based on semantic similarity using Vector Embeddings.
    
    Args:
        params (SearchQueryInput): Validated input containing:
            - query (str): The semantic search query string.
            
    Returns:
        str: JSON-formatted string containing an array of matched chunks. Each chunk includes
             the exact 'text' and 'meta' data (which has 'url' and 'title').
    '''
    try:
        results = rag_system.search(params.query, top_k=3)
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error performing search: {str(e)}"

if __name__ == "__main__":
    # If PORT is set (like on Railway), we run as a Web API (SSE)
    if "PORT" in os.environ:
        print(f"🚀 Starting MCP Server on port {port} (Railway Deployment Mode)...")
        mcp.run(transport="sse")
    else:
        # Otherwise run locally using standard input/output (for Cursor & Claude)
        mcp.run(transport="stdio")
