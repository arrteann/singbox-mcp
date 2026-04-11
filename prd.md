# 📄 Product Requirements Document (PRD)

## 🧩 1. Overview

### 🟢 Product Name:

Sing-box Documentation RAG MCP Server

### 🟢 Description:

سیستمی که داکیومنت‌های sing-box را به صورت خودکار جمع‌آوری (scrape)، پردازش (RAG) و از طریق یک MCP-compatible API در اختیار مدل‌های هوش مصنوعی قرار می‌دهد.

### 🟢 Goals:

* دسترسی دقیق و semantic به داکیومنت sing-box
* کاهش hallucination مدل‌ها
* فراهم کردن API برای ابزارهای AI (Claude, Cursor, etc.)

---

## 🎯 2. Objectives

### Functional Objectives:

1. استخراج کامل داکیومنت‌ها از سایت
2. تبدیل به داده ساختاریافته
3. پیاده‌سازی RAG برای جستجوی semantic
4. ارائه API استاندارد MCP

### Non-Functional Objectives:

* latency کم (< 1s)
* دقت بالا در retrieval
* قابلیت deploy رایگان
* مقیاس‌پذیری

---

## 👤 3. Target Users

* توسعه‌دهندگان Xray / sing-box
* کاربران DevOps
* ابزارهای AI (LLMs)
* کاربران MCP-compatible apps

---

## 🧱 4. System Architecture

### High-Level:

User → LLM → MCP Server → RAG Engine → Vector DB → Scraped Docs

---

### Components:

#### 1. Scraper

* استخراج لینک‌ها از navigation
* خواندن `<main>`
* تبدیل به structured data

#### 2. Processor

* chunking
* embedding
* metadata tagging

#### 3. Vector Store

* FAISS (local)
  یا
* external DB (optional)

#### 4. RAG Engine

* semantic search
* top-k retrieval

#### 5. MCP Server (API)

* endpoint برای tool calling
* interface استاندارد MCP

---

## 🔧 5. Functional Requirements

### 5.1 Scraper

* استخراج لینک‌های `/configuration/`
* حذف لینک‌های غیرمرتبط
* پشتیبانی از nested routes
* استخراج:

  * headings
  * paragraphs
  * code blocks
  * lists

---

### 5.2 Data Processing

* تبدیل content به chunk
* chunk size: 300–700 characters
* optional overlap

---

### 5.3 Embedding

* استفاده از SentenceTransformer
* مدل: all-MiniLM-L6-v2

---

### 5.4 Vector Index

* FAISS IndexFlatL2
* ذخیره روی دیسک

---

### 5.5 Search (RAG)

* ورودی: query string
* خروجی:

  * top-k chunks
  * metadata (url, title)

---

### 5.6 MCP API

#### Endpoint:

POST /call_tool

#### Input:

```json
{
  "name": "search_docs",
  "arguments": {
    "query": "inbound config"
  }
}
```

#### Output:

```json
[
  {
    "text": "...",
    "meta": {
      "url": "...",
      "title": "Inbound"
    }
  }
]
```

---

## ⚙️ 6. Non-Functional Requirements

### Performance:

* response time < 1s
* index build < 2 min

### Reliability:

* fallback در صورت خطا در scrape
* log errors

### Scalability:

* امکان migration به Pinecone / Weaviate

---

## 📦 7. Data Model

### Document:

```json
{
  "url": "string",
  "title": "string",
  "content": "string"
}
```

---

### Chunk:

```json
{
  "text": "string",
  "embedding": [float],
  "meta": {
    "url": "string",
    "title": "string"
  }
}
```

---

## 🔄 8. Data Flow

1. Scraper → raw HTML
2. Parser → structured content
3. Chunker → small text blocks
4. Embedder → vectors
5. Index → FAISS
6. Query → embedding
7. Retrieval → top-k chunks

---

## 🚀 9. Deployment

### Recommended:

* Railway (free tier)

### Requirements:

* Python runtime
* RAM ≥ 512MB

---

## ⚠️ 10. Risks

| Risk               | Description           | Mitigation      |
| ------------------ | --------------------- | --------------- |
| سایت تغییر کند     | HTML structure breaks | selector update |
| memory limit       | FAISS RAM usage       | chunk reduce    |
| inaccurate results | bad embedding         | better model    |

---

## 🔮 11. Future Improvements

* Hybrid search (keyword + semantic)
* Re-ranking
* Auto config generator for sing-box
* Real-time doc sync
* Multi-language support

---

## 🧪 12. Success Metrics

* Retrieval accuracy > 85%
* Response latency < 1s
* Coverage of docs > 95%

---

## 📌 13. MVP Scope

Included:

* scraper
* RAG (FAISS)
* MCP API

Excluded:

* UI
* auth
* multi-tenant support

---

# ✅ End of PRD
