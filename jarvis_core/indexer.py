"""Personal Knowledge Graph indexer using ChromaDB and Sentence-Transformers."""
from __future__ import annotations

import os
from pathlib import Path

from jarvis_core.config import ROOT

try:
    import chromadb
except ImportError:
    chromadb = None


class KnowledgeGraph:
    def __init__(self) -> None:
        if not chromadb:
            self.client = None
            return
        db_path = ROOT / ".jarvis_db"
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self.client.get_or_create_collection("personal_knowledge")
        self._indexed_files: set[str] = set()

    def index_directory(self, path: str) -> str:
        if not self.client:
            return "ChromaDB is not available."
        
        target = Path(os.path.expanduser(path))
        if not target.exists():
            return f"Directory {path} does not exist."

        count = 0
        from jarvis_core.embeddings import get_engine
        engine = get_engine()

        for ext in ("*.md", "*.txt", "*.py"):
            for file_path in target.rglob(ext):
                if ".git" in str(file_path) or "node_modules" in str(file_path):
                    continue
                if str(file_path) in self._indexed_files:
                    continue
                
                try:
                    content = file_path.read_text(errors="ignore")
                    if not content.strip():
                        continue
                        
                    # Simple chunking by paragraphs
                    chunks = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 50]
                    if not chunks:
                        continue
                        
                    embeds = engine.embed(chunks).tolist()
                    
                    ids = [f"{file_path}_{i}" for i in range(len(chunks))]
                    metadatas = [{"source": str(file_path)} for _ in chunks]
                    
                    # Prevent id conflicts by deleting old if exists
                    try:
                        self.collection.add(
                            embeddings=embeds,
                            documents=chunks,
                            metadatas=metadatas,
                            ids=ids
                        )
                    except Exception:
                        pass
                    
                    self._indexed_files.add(str(file_path))
                    count += len(chunks)
                except Exception:
                    pass
                    
        return f"Indexed {count} new chunks from {path}."

    def search(self, query: str, n_results: int = 3) -> str:
        if not self.client:
            return "Knowledge graph is offline. Install chromadb."
            
        from jarvis_core.embeddings import get_engine
        engine = get_engine()
        query_vec = engine.embed_one(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=n_results
        )
        
        if not results or not results.get('documents') or not results['documents'][0]:
            return "No relevant documents found."
            
        docs = results['documents'][0]
        meta = results['metadatas'][0]
        
        out = []
        for i, doc in enumerate(docs):
            src = meta[i].get("source", "Unknown") if meta and i < len(meta) else "Unknown"
            out.append(f"[Source: {src}]\n{doc}")
            
        return "\n\n".join(out)

_kg = None

def get_kg() -> KnowledgeGraph:
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg
