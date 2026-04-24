import os
# Use Hugging Face mirror to avoid network blocks
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
OVERLAP = 100
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "faiss_index.bin")
METADATA_FILE = os.path.join(BASE_DIR, "metadata.pkl")
DATA_FILE = os.path.join(BASE_DIR, "data.json")

class RAGSystem:
    def __init__(self, data_path=DATA_FILE):
        self.data_path = data_path
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.index = None
        self.metadata = []

    def load_data(self):
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file '{self.data_path}' not found. Please run scrapper.py first.")
        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def chunk_text(self, text, url, title):
        """
        Splits text into chunks of CHUNK_SIZE characters, with an OVERLAP.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end]
            
            # Optionally, you can find the nearest newline to avoid cutting words/sentences in half,
            # but for simplicity, we do standard character-level overlapping chunks.
            chunks.append({
                "text": chunk_text,
                "url": url,
                "title": title
            })
            
            # Step forward by chunk size minus overlap
            start += (CHUNK_SIZE - OVERLAP)
        return chunks

    def build_index(self):
        """
        Reads data.json, chunks the content, creates embeddings, and builds a FAISS index.
        """
        print("Loading scraped data...")
        data = self.load_data()
        
        print(f"Chunking documents (Size: {CHUNK_SIZE}, Overlap: {OVERLAP})...")
        all_chunks = []
        for doc in data:
            chunks = self.chunk_text(doc["content"], doc["url"], doc["title"])
            all_chunks.extend(chunks)
            
        print(f"Created {len(all_chunks)} chunks from {len(data)} documents.")
        
        print(f"Generating embeddings using {EMBEDDING_MODEL} (this may take a moment)...")
        texts = [c["text"] for c in all_chunks]
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Define dimension of embeddings
        dimension = embeddings.shape[1]
        
        print("Building FAISS index...")
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        self.metadata = all_chunks
        
        print("Saving FAISS index and metadata to disk...")
        faiss.write_index(self.index, INDEX_FILE)
        with open(METADATA_FILE, "wb") as f:
            pickle.dump(self.metadata, f)
            
        print("✅ Index build successfully completed!\n")

    def load_index(self):
        """
        Loads the FAISS index and chunk metadata from disk.
        """
        if not os.path.exists(INDEX_FILE) or not os.path.exists(METADATA_FILE):
             raise FileNotFoundError("FAISS index or metadata not found. Please build the index first.")
             
        self.index = faiss.read_index(INDEX_FILE)
        with open(METADATA_FILE, "rb") as f:
            self.metadata = pickle.load(f)

    def search(self, query, top_k=3):
        """
        Takes a query string, embeddings it, and returns the top_k matching chunks.
        """
        if self.index is None:
            self.load_index()
            
        # Embed the search query
        query_vector = self.model.encode([query], convert_to_numpy=True)
        
        # Search the index (L2 distance: lower distance = more similar)
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.metadata):
                res = self.metadata[idx]
                results.append({
                    "text": res["text"],
                    "meta": {
                        "url": res["url"],
                        "title": res["title"]
                    }
                })
        return results

if __name__ == "__main__":
    system = RAGSystem()
    
    # 1. Build the index (only needed once, or when data.json updates)
    system.build_index()
    
    # 2. Test a sample query
    test_query = "How to configure inbound sniffing?"
    print(f"--- Testing Search RAG ---")
    print(f"Query: '{test_query}'\n")
    
    results = system.search(test_query, top_k=3)
    for i, r in enumerate(results, 1):
        print(f"--- Result {i} ---")
        print(f"📘 Title: {r['meta']['title']}")
        print(f"🔗 URL: {r['meta']['url']}")
        print(f"📝 Text Snippet:\n{r['text']}")
        print("-" * 50 + "\n")
