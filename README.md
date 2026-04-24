# Sing-box Documentation RAG MCP Server 🚀

A highly efficient local AI system that extracts, semantically indexes, and serves [sing-box](https://sing-box.sagernet.org/) documentation via the Model Context Protocol (MCP). This enables AI tools like Cursor and Claude Desktop to fetch real-time, accurate configurations and avoid "AI hallucinations".

## 🌟 Features
- **Automated Web Scrapper**: Crawls the official sing-box website and extracts structured documentation sections.
- **Local RAG Pipeline (100% Free)**: Uses `SentenceTransformers` (`all-MiniLM-L6-v2`) to turn text into embeddings.
- **Fast Semantic Search**: Stores knowledge inside a lightweight local `FAISS` Vector Database for <100ms semantic search.
- **MCP API API Integration**: Built with `FastMCP` to provide AI-readable functions over standard input (`stdio`) or HTTP Server-Sent Events (`sse`).
- **Cloud-Ready Deployment**: Ready to be uploaded and hosted on Railway to act as a public MCP tool.

## 📦 Project Architecture
```text
├── scrapper.py       # Scrapes documentation site into data.json
├── rag.py            # Chunks data, downloads ML models, builds FAISS index
├── server.py         # MCP API server (handles stdio and sse transport)
├── requirements.txt  # Dependencies (Railway ready)
└── prd.md            # Product Requirements Document
```

---

## 🛠️ Installation

### 1. Requirements
- macOS/Linux/Windows
- Python 3.10+
- (Optional but recommended) Virtual Environment

### 2. Setup
Create a virtual environment and load the dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🚀 How to Build the Database (RAG)

Before querying the AI, you must build the FAISS index database:
1. **Scrape the documentation:**
    ```bash
    python3 scrapper.py
    ```
    *(This creates `data.json`)*
2. **Build FAISS Index:**
    ```bash
    python3 rag.py
    ```
    *(This downloads the transformer model, generates embeddings, and creates `faiss_index.bin`)*

---

## 🔗 Connecting to AI (Cursor & Claude)

You can plug this server into your intelligent IDE or Desktop assistant automatically.

### For Cursor CLI/IDE
1. Open Cursor Settings (`Cmd + Shift + J`).
2. Go to **Features** -> **MCP Servers**.
3. Click `+ Add New MCP Server`.
4. Use the following:
   - **Name**: `singbox-docs`
   - **Type**: `command`
   - **Command**: `/path/to/your/venv/bin/python /path/to/your/server.py`

### For Claude Desktop App
Add the following to your `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "singbox_docs": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/server.py"
      ]
    }
  }
}
```

---

## ☁️ Deployment (Railway)
This project is configured out-of-the-box for Cloud Deployments. 

By default, executing `server.py` checks for the environment variable `PORT`. If the variable exists (like on Railway), the `FastMCP` server automatically switches to the `SSE` (Server-Sent Events) HTTP Transport protocol!

**Deployment Steps:**
1. Commit the repository to GitHub.
2. Link the repository to your [Railway.app](https://railway.app/).
3. Railway will detect `requirements.txt` and install Python modules.
4. Set the Start Command (or `Procfile`) to:
   ```bash
   python server.py
   ```
5. Railway provides you a domain (e.g. `https://my-singbox-mcp.up.railway.app/sse`). You can now instruct Claude or external AI agents to access your API globally.
