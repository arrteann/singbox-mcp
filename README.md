# Sing-box Documentation RAG MCP Server

Local RAG pipeline that scrapes [sing-box](https://sing-box.sagernet.org/) docs, indexes them with hybrid search (FAISS + BM25), and serves them over MCP for Cursor / Claude.

## Features
- **Scraper**: Crawls `/configuration/` and extracts headings, prose, lists, and code blocks
- **Section-aware chunking**: Splits on markdown headings with breadcrumb context (not blind character windows)
- **Hybrid retrieval**: Dense FAISS search + BM25 keyword search, fused with Reciprocal Rank Fusion
- **Scored MCP tool**: Returns fused / semantic / BM25 scores plus `heading_path`
- **Package layout**: Installable `src/singbox_mcp` with CLI (`singbox-mcp` / `python -m singbox_mcp`)

## Project layout
```text
├── src/singbox_mcp/
│   ├── scraper.py      # Crawl docs → data.json
│   ├── rag.py          # Section chunking, FAISS + BM25, hybrid search
│   ├── server.py       # FastMCP tool server
│   └── __main__.py     # CLI: scrape | build-index | serve
├── scrapper.py         # Thin backward-compatible wrappers
├── rag.py
├── server.py
├── pyproject.toml
├── requirements.txt
└── prd.md
```

## Installation

Python 3.10+ recommended.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
# or: pip install -r requirements.txt && pip install -e .
```

## Build the index

```bash
python -m singbox_mcp scrape        # writes data.json
python -m singbox_mcp build-index   # writes faiss_index.bin + metadata.pkl
```

Legacy scripts still work (`python scrapper.py`, `python rag.py`) after `pip install -e .`.

Generated index files are gitignored — rebuild them locally or in CI/deploy.

### Useful env vars
| Variable | Default | Purpose |
|---|---|---|
| `SINGBOX_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `SINGBOX_CHUNK_SIZE` | `700` | Max chars per section piece |
| `SINGBOX_CHUNK_OVERLAP` | `120` | Overlap for oversized sections |
| `SINGBOX_TOP_K` | `5` | Default result count |
| `HF_ENDPOINT` | `https://hf-mirror.com` | Hugging Face endpoint / mirror |

## Run the MCP server

```bash
python -m singbox_mcp serve
# or: singbox-mcp serve
```

- No `PORT` → stdio (Cursor / Claude Desktop)
- `PORT` set → SSE HTTP (Railway-style deploy)

### Cursor
- **Name**: `singbox-docs`
- **Type**: `command`
- **Command**: `/path/to/venv/bin/python -m singbox_mcp serve`

### Claude Desktop
```json
{
  "mcpServers": {
    "singbox_docs": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "singbox_mcp", "serve"]
    }
  }
}
```

### Tool: `search_docs`
Arguments:
- `query` (required)
- `top_k` (optional, 1–20)
- `mode`: `hybrid` | `semantic` | `keyword`

Each hit includes `text`, `score`, per-channel `scores`, and `meta` (`url`, `title`, `section`, `heading_path`).

## Tests / CI
```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
```

GitHub Actions runs the same suite on Python 3.10 and 3.12 for every PR.

## Deployment (Railway)
1. Push the repo
2. Install deps from `requirements.txt` / `pyproject.toml`
3. Run scrape + build-index in a release/build step (or bake artifacts into the image)
4. Start command: `python -m singbox_mcp serve`

Railway sets `PORT`, so the server uses SSE automatically.
