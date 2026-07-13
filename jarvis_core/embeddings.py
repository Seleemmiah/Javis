"""Embedding engine — sentence-transformers (semantic) with TF-IDF fallback."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional

import numpy as np

_TOKEN = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class EmbeddingEngine:
    """Lazy-loaded semantic embeddings with offline TF-IDF fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._available: Optional[bool] = None

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts. Returns (N, dim) float32 array."""
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        if self.available():
            model = self._load_model()
            return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # TF-IDF fallback
        return self._tfidf_embed(texts)

    def embed_one(self, text: str) -> np.ndarray:
        """Embed a single text. Returns (dim,) array."""
        return self.embed([text])[0]

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two 1-D vectors."""
        dot = float(np.dot(a, b))
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def cosine_similarities(self, query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
        """Cosine similarities between a query vector and a matrix of corpus vectors."""
        if corpus_vecs.shape[0] == 0:
            return np.array([], dtype=np.float32)
        qn = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True) + 1e-10
        cn = corpus_vecs / norms
        return cn @ qn

    # --- TF-IDF fallback ---
    def _tfidf_embed(self, texts: list[str], dim: int = 384) -> np.ndarray:
        """Build pseudo-embeddings using hashed TF-IDF."""
        all_tokens: list[list[str]] = [_tokenize(t) for t in texts]
        df: Counter[str] = Counter()
        for tokens in all_tokens:
            df.update(set(tokens))
        n = max(len(texts), 1)
        idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

        vecs = np.zeros((len(texts), dim), dtype=np.float32)
        for i, tokens in enumerate(all_tokens):
            if not tokens:
                continue
            tf = Counter(tokens)
            total = len(tokens)
            for t, count in tf.items():
                weight = (count / total) * idf.get(t, 1.0)
                idx = hash(t) % dim
                vecs[i, idx] += weight
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
        vecs = vecs / norms
        return vecs


_engine: Optional[EmbeddingEngine] = None


def get_engine() -> EmbeddingEngine:
    global _engine
    if _engine is None:
        _engine = EmbeddingEngine()
    return _engine
