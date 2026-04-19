"""Embedding utilities for Sinhala hybrid RAG."""

from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class EmbeddingConfig:
    """Configuration for the sentence transformer embedder."""

    model_name: str = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    local_files_only: bool = os.getenv("EMBEDDING_LOCAL_ONLY", "1") == "1"


class SinhalaEmbedder:
    """Sinhala-safe embedding model wrapper with offline-only defaults."""

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()
        try:
            self.model = SentenceTransformer(
                self.config.model_name,
                local_files_only=self.config.local_files_only,
            )
        except Exception as exc:
            raise RuntimeError(
                "Embedding model could not be loaded in offline mode. "
                "Pre-download or provide a local model path via EMBEDDING_MODEL_NAME."
            ) from exc

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode text list into float32 embeddings."""
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query preserving 2D shape for FAISS."""
        return self.encode([query])

    @staticmethod
    def l2_normalize(vectors: np.ndarray) -> np.ndarray:
        """Return L2-normalized vectors for cosine similarity with dot product."""
        if vectors.size == 0:
            return vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-12, norms)
        return vectors / norms
