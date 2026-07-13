"""Long-term semantic memory — vector embeddings with TF-IDF fallback."""

from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

from jarvis_core.config import LONG_TERM_MEMORY_FILE, CACHE_DIR

_TOKEN = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class LongTermMemory:
    """
    Stores facts, preferences, events, and conversation snippets.
    Retrieval uses semantic vector embeddings (sentence-transformers)
    with TF-IDF cosine similarity as offline fallback.
    """

    def __init__(self, path=LONG_TERM_MEMORY_FILE) -> None:
        self.path = path
        self.entries: list[dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._embed_path = CACHE_DIR / "memory_embeddings.npy"
        self._engine = None
        self._load()

    def _get_engine(self):
        if self._engine is None:
            from jarvis_core.embeddings import get_engine
            self._engine = get_engine()
        return self._engine

    def _load(self) -> None:
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self.entries = data if isinstance(data, list) else data.get("entries", [])
        except (OSError, json.JSONDecodeError):
            self.entries = []
        # Load cached embeddings
        try:
            if self._embed_path.exists():
                self._embeddings = np.load(str(self._embed_path))
                if self._embeddings.shape[0] != len(self.entries):
                    self._embeddings = None
        except Exception:
            self._embeddings = None

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2)
        if self._embeddings is not None:
            try:
                np.save(str(self._embed_path), self._embeddings)
            except Exception:
                pass

    def _rebuild_embeddings(self) -> None:
        """Rebuild full embedding matrix from all entries."""
        if not self.entries:
            self._embeddings = None
            return
        engine = self._get_engine()
        texts = [e.get("text", "") for e in self.entries]
        self._embeddings = engine.embed(texts)

    def _ensure_embeddings(self) -> np.ndarray:
        """Ensure embeddings are available, rebuilding if needed."""
        if self._embeddings is None or self._embeddings.shape[0] != len(self.entries):
            self._rebuild_embeddings()
        if self._embeddings is not None:
            return self._embeddings
        return np.zeros((0, 384), dtype=np.float32)

    def add(
        self,
        text: str,
        kind: str = "note",
        tags: Optional[list[str]] = None,
        meta: Optional[dict] = None,
    ) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        # de-dupe near-identical
        for e in self.entries[-50:]:
            if e.get("text", "").strip().lower() == text.lower():
                return e["id"]
        eid = uuid.uuid4().hex[:12]
        self.entries.append(
            {
                "id": eid,
                "text": text,
                "kind": kind,
                "tags": tags or [],
                "meta": meta or {},
                "created": datetime.now().isoformat(),
            }
        )
        # Append embedding for new entry
        engine = self._get_engine()
        new_vec = engine.embed_one(text)
        if self._embeddings is not None and self._embeddings.shape[0] == len(self.entries) - 1:
            self._embeddings = np.vstack([self._embeddings, new_vec.reshape(1, -1)])
        else:
            self._embeddings = None
        # cap growth
        if len(self.entries) > 2000:
            self.entries = self.entries[-2000:]
            self._embeddings = None
        self.save()
        return eid

    def remember_fact(self, fact: str) -> str:
        return self.add(fact, kind="fact")

    def remember_preference(self, pref: str) -> str:
        return self.add(pref, kind="preference")

    def remember_event(self, event: str) -> str:
        return self.add(event, kind="event")

    def forget(self, entry_id: str) -> bool:
        """Remove a memory by ID."""
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.get("id") != entry_id]
        if len(self.entries) < before:
            self._embeddings = None
            self.save()
            return True
        return False

    def forget_by_text(self, substring: str) -> int:
        """Remove all memories containing the substring. Returns count removed."""
        sub = substring.lower()
        before = len(self.entries)
        self.entries = [
            e for e in self.entries if sub not in e.get("text", "").lower()
        ]
        removed = before - len(self.entries)
        if removed > 0:
            self._embeddings = None
            self.save()
        return removed

    def search(self, query: str, k: int = 5, min_score: float = 0.05) -> list[dict[str, Any]]:
        if not self.entries or not query.strip():
            return []

        engine = self._get_engine()
        embeddings = self._ensure_embeddings()

        if embeddings.shape[0] == 0:
            return self._search_tfidf_fallback(query, k, min_score)

        query_vec = engine.embed_one(query)
        scores = engine.cosine_similarities(query_vec, embeddings)

        scored = []
        for i, score_val in enumerate(scores):
            s = float(score_val)
            if query.lower() in self.entries[i].get("text", "").lower():
                s += 0.15
            if s >= min_score:
                scored.append({**self.entries[i], "score": round(s, 4)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def _search_tfidf_fallback(
        self, query: str, k: int = 5, min_score: float = 0.05
    ) -> list[dict[str, Any]]:
        """Pure-Python TF-IDF fallback when embeddings aren't available."""
        idf = self._idf()
        qv = self._tfidf_vec(query, idf)
        scored = []
        for e in self.entries:
            ev = self._tfidf_vec(e.get("text", ""), idf)
            score = self._cos(qv, ev)
            if query.lower() in e.get("text", "").lower():
                score += 0.15
            if score >= min_score:
                scored.append({**e, "score": round(score, 4)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def _idf(self) -> dict[str, float]:
        df: Counter[str] = Counter()
        for e in self.entries:
            df.update(set(_tokenize(e.get("text", ""))))
        n = max(len(self.entries), 1)
        return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def _tfidf_vec(self, text: str, idf: dict[str, float]) -> dict[str, float]:
        tokens = _tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        return {t: (tf[t] / total) * idf.get(t, 1.0) for t in tf}

    @staticmethod
    def _cos(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        keys = set(a) | set(b)
        dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def context_block(self, query: str, k: int = 5) -> str:
        hits = self.search(query, k=k)
        if not hits:
            recent = [e for e in self.entries if e.get("kind") in ("fact", "preference")][-5:]
            if not recent:
                return ""
            lines = [f"- ({e['kind']}) {e['text']}" for e in recent]
            return "Known about user (recent):\n" + "\n".join(lines)
        lines = [
            f"- [{h['kind']}|{h['score']}] {h['text']}"
            for h in hits
        ]
        return "Relevant long-term memory:\n" + "\n".join(lines)

    def summarize_memories(self, kind: Optional[str] = None, limit: int = 20) -> str:
        """Summarize stored memories, optionally filtered by kind."""
        entries = self.entries
        if kind:
            entries = [e for e in entries if e.get("kind") == kind]
        if not entries:
            return f"No {'memories' if not kind else kind + ' memories'} stored."
        recent = entries[-limit:]
        lines = []
        for e in recent:
            created = e.get("created", "unknown")[:10]
            lines.append(f"- [{e.get('kind', 'note')}] ({created}) {e['text'][:100]}")
        total = len(entries)
        header = f"Showing {len(recent)} of {total} {'memories' if not kind else kind + ' memories'}:\n"
        return header + "\n".join(lines)

    def summary_stats(self) -> str:
        kinds = Counter(e.get("kind", "note") for e in self.entries)
        parts = ", ".join(f"{k}={v}" for k, v in kinds.items())
        engine = self._get_engine()
        engine_type = "semantic" if engine.available() else "TF-IDF"
        return f"{len(self.entries)} memories ({parts or 'empty'}) [{engine_type}]"
