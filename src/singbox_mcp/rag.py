"""Section-aware chunking, FAISS semantic search, and hybrid BM25 retrieval."""

from __future__ import annotations

import json
import logging
import os
import pickle
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# Optional mirror for restricted networks; override with HF_ENDPOINT env.
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.environ.get("SINGBOX_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
MAX_CHUNK_CHARS = int(os.environ.get("SINGBOX_CHUNK_SIZE", "700"))
CHUNK_OVERLAP = int(os.environ.get("SINGBOX_CHUNK_OVERLAP", "120"))
DEFAULT_TOP_K = int(os.environ.get("SINGBOX_TOP_K", "5"))
HYBRID_CANDIDATE_MULTIPLIER = 3
RRF_K = 60

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_FILE = Path(os.environ.get("SINGBOX_INDEX_FILE", REPO_ROOT / "faiss_index.bin"))
METADATA_FILE = Path(os.environ.get("SINGBOX_METADATA_FILE", REPO_ROOT / "metadata.pkl"))
DATA_FILE = Path(os.environ.get("SINGBOX_DATA_FILE", REPO_ROOT / "data.json"))

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]*", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


def _split_oversized_section(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split long sections on paragraph boundaries when possible."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush()
        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            if end < len(paragraph):
                break_at = paragraph.rfind("\n", start, end)
                if break_at <= start + max_chars // 3:
                    break_at = paragraph.rfind(" ", start, end)
                if break_at > start + max_chars // 3:
                    end = break_at
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start = max(end - overlap, start + 1)

        current = ""

    flush()
    return chunks


def chunk_document(
    content: str,
    url: str,
    title: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Split a markdown-ish doc into heading-aware chunks with breadcrumb context."""
    matches = list(HEADING_RE.finditer(content))
    chunks: list[dict[str, Any]] = []

    if not matches:
        for idx, piece in enumerate(_split_oversized_section(content, max_chars, overlap)):
            chunks.append(
                {
                    "text": piece,
                    "url": url,
                    "title": title,
                    "section": title,
                    "heading_path": title,
                    "chunk_index": idx,
                }
            )
        return chunks

    # Preface before the first heading
    preface = content[: matches[0].start()].strip()
    heading_stack: list[tuple[int, str]] = []

    sections: list[tuple[str, str, str]] = []
    if preface:
        sections.append((title, title, preface))

    for i, match in enumerate(matches):
        level = len(match.group(1))
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, heading))
        path = " > ".join(part for _, part in heading_stack)
        section_text = f"{'#' * level} {heading}\n\n{body}".strip()
        sections.append((heading, path, section_text))

    chunk_index = 0
    for section_title, heading_path, section_text in sections:
        breadcrumb = f"[{title}] {heading_path}" if heading_path != title else f"[{title}]"
        for piece in _split_oversized_section(section_text, max_chars, overlap):
            text = f"{breadcrumb}\n\n{piece}".strip()
            chunks.append(
                {
                    "text": text,
                    "url": url,
                    "title": title,
                    "section": section_title,
                    "heading_path": heading_path,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

    return chunks


def _l2_to_similarity(distance: float) -> float:
    """Map FAISS L2 distance to a bounded similarity score in (0, 1]."""
    return float(1.0 / (1.0 + max(distance, 0.0)))


def reciprocal_rank_fusion(
    ranked_lists: list[list[int]],
    k: int = RRF_K,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


class RAGSystem:
    def __init__(self, data_path: str | Path = DATA_FILE):
        self.data_path = Path(data_path)
        self._model: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self.metadata: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
        self._tokenized_corpus: list[list[str]] = []

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        return self._model

    def load_data(self) -> list[dict[str, str]]:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Data file '{self.data_path}' not found. Please run the scraper first."
            )
        with self.data_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _rebuild_bm25(self) -> None:
        self._tokenized_corpus = [tokenize(chunk["text"]) for chunk in self.metadata]
        self._bm25 = BM25Okapi(self._tokenized_corpus) if self._tokenized_corpus else None

    def build_index(self) -> None:
        logger.info("Loading scraped data from %s", self.data_path)
        data = self.load_data()

        logger.info(
            "Chunking documents by section (max_chars=%s, overlap=%s)",
            MAX_CHUNK_CHARS,
            CHUNK_OVERLAP,
        )
        all_chunks: list[dict[str, Any]] = []
        for doc in data:
            all_chunks.extend(chunk_document(doc["content"], doc["url"], doc["title"]))

        logger.info("Created %s chunks from %s documents", len(all_chunks), len(data))

        logger.info("Generating embeddings using %s", EMBEDDING_MODEL)
        texts = [chunk["text"] for chunk in all_chunks]
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        embeddings = np.asarray(embeddings, dtype=np.float32)

        dimension = embeddings.shape[1]
        logger.info("Building FAISS index (dim=%s)", dimension)
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        self.metadata = all_chunks
        self._rebuild_bm25()

        logger.info("Saving FAISS index to %s and metadata to %s", INDEX_FILE, METADATA_FILE)
        faiss.write_index(self.index, str(INDEX_FILE))
        with METADATA_FILE.open("wb") as handle:
            pickle.dump(
                {
                    "version": 2,
                    "embedding_model": EMBEDDING_MODEL,
                    "chunks": self.metadata,
                },
                handle,
            )

        logger.info("Index build completed")

    def load_index(self) -> None:
        if not INDEX_FILE.exists() or not METADATA_FILE.exists():
            raise FileNotFoundError("FAISS index or metadata not found. Please build the index first.")

        self.index = faiss.read_index(str(INDEX_FILE))
        with METADATA_FILE.open("rb") as handle:
            payload = pickle.load(handle)

        # Backward compatible with legacy list-only pickle
        if isinstance(payload, list):
            self.metadata = payload
        else:
            self.metadata = payload.get("chunks", [])

        self._rebuild_bm25()

    def _ensure_ready(self, *, need_faiss: bool = True) -> None:
        if need_faiss:
            if self.index is None or not self.metadata:
                self.load_index()
        elif not self.metadata:
            self.load_index()
        if self._bm25 is None and self.metadata:
            self._rebuild_bm25()

    def _semantic_ranks(self, query: str, candidate_k: int) -> tuple[list[int], dict[int, float]]:
        assert self.index is not None
        query_vector = self.model.encode([query], convert_to_numpy=True)
        query_vector = np.asarray(query_vector, dtype=np.float32)
        distances, indices = self.index.search(query_vector, candidate_k)

        ranked: list[int] = []
        scores: dict[int, float] = {}
        for distance, idx in zip(distances[0], indices[0], strict=True):
            if idx == -1 or idx >= len(self.metadata):
                continue
            ranked.append(int(idx))
            scores[int(idx)] = _l2_to_similarity(float(distance))
        return ranked, scores

    def _bm25_ranks(self, query: str, candidate_k: int) -> tuple[list[int], dict[int, float]]:
        if self._bm25 is None:
            return [], {}

        tokens = tokenize(query)
        if not tokens:
            return [], {}

        scores_arr = self._bm25.get_scores(tokens)
        top_n = min(candidate_k, len(scores_arr))
        if top_n <= 0:
            return [], {}

        top_indices = np.argpartition(scores_arr, -top_n)[-top_n:]
        ordered = sorted(top_indices.tolist(), key=lambda i: scores_arr[i], reverse=True)

        max_score = float(scores_arr[ordered[0]]) if ordered else 0.0
        scores: dict[int, float] = {}
        ranked: list[int] = []
        for idx in ordered:
            raw = float(scores_arr[idx])
            if raw <= 0:
                continue
            ranked.append(idx)
            scores[idx] = raw / max_score if max_score > 0 else 0.0
        return ranked, scores

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        mode: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """
        Search the index.

        mode:
          - semantic: FAISS dense retrieval only
          - keyword: BM25 only
          - hybrid: Reciprocal Rank Fusion of both (default)
        """
        mode = (mode or "hybrid").lower()
        need_faiss = mode not in {"keyword", "bm25"}
        need_bm25 = mode != "semantic"
        self._ensure_ready(need_faiss=need_faiss)
        candidate_k = max(top_k * HYBRID_CANDIDATE_MULTIPLIER, top_k)

        semantic_ranked: list[int] = []
        semantic_scores: dict[int, float] = {}
        bm25_ranked: list[int] = []
        bm25_scores: dict[int, float] = {}

        if need_faiss:
            semantic_ranked, semantic_scores = self._semantic_ranks(query, candidate_k)
        if need_bm25:
            bm25_ranked, bm25_scores = self._bm25_ranks(query, candidate_k)

        if mode == "semantic":
            ordered_ids = semantic_ranked[:top_k]
            fusion_scores = {idx: semantic_scores.get(idx, 0.0) for idx in ordered_ids}
        elif mode in {"keyword", "bm25"}:
            ordered_ids = bm25_ranked[:top_k]
            fusion_scores = {idx: bm25_scores.get(idx, 0.0) for idx in ordered_ids}
        else:
            fusion_scores = reciprocal_rank_fusion([semantic_ranked, bm25_ranked])
            ordered_ids = sorted(fusion_scores, key=fusion_scores.get, reverse=True)[:top_k]

        results: list[dict[str, Any]] = []
        for idx in ordered_ids:
            chunk = self.metadata[idx]
            results.append(
                {
                    "text": chunk["text"],
                    "score": round(float(fusion_scores.get(idx, 0.0)), 6),
                    "scores": {
                        "semantic": round(float(semantic_scores.get(idx, 0.0)), 6),
                        "bm25": round(float(bm25_scores.get(idx, 0.0)), 6),
                        "fused": round(float(fusion_scores.get(idx, 0.0)), 6),
                    },
                    "meta": {
                        "url": chunk["url"],
                        "title": chunk["title"],
                        "section": chunk.get("section", chunk["title"]),
                        "heading_path": chunk.get("heading_path", chunk["title"]),
                        "chunk_index": chunk.get("chunk_index", 0),
                    },
                }
            )
        return results


def main() -> None:
    system = RAGSystem()
    system.build_index()

    test_query = "How to configure inbound sniffing?"
    logger.info("Smoke search query=%r", test_query)
    results = system.search(test_query, top_k=3, mode="hybrid")
    for i, result in enumerate(results, 1):
        logger.info(
            "Result %s score=%.4f title=%s section=%s",
            i,
            result["score"],
            result["meta"]["title"],
            result["meta"]["heading_path"],
        )
        logger.info("Snippet: %s", result["text"][:240].replace("\n", " "))


if __name__ == "__main__":
    from .logging_config import setup_logging

    setup_logging()
    main()
