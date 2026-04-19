"""Semantic retriever for unstructured Sinhala text documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np

from chatbot.embeddings import SinhalaEmbedder


@dataclass
class TextChunk:
    """Single chunk from a text document."""

    topic: str
    source: str
    content: str


@dataclass
class TextHit:
    """Retrieved text match."""

    topic: str
    source: str
    content: str
    score: float


class TextRetriever:
    """FAISS retriever over topic documents with topic-filtered search."""

    def __init__(
        self,
        documents_dir: Path,
        index_path: Path,
        metadata_path: Path,
        vectors_path: Path,
        rebuild: bool = False,
    ) -> None:
        self.documents_dir = documents_dir
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.vectors_path = vectors_path
        self.embedder = SinhalaEmbedder()

        self.chunks = self._load_chunks()
        if not self.chunks:
            raise ValueError("No valid text chunks found in data/documents")

        if rebuild or not self.index_path.exists() or not self.metadata_path.exists() or not self.vectors_path.exists():
            self.index, self.vectors = self._build_index()
        else:
            self.index, self.vectors = self._load_index_or_rebuild()

    @staticmethod
    def _parse_topic(file_text: str, default_topic: str) -> tuple[str, str]:
        lines = file_text.splitlines()
        if not lines:
            return default_topic, ""

        first = lines[0].strip()
        if first.startswith("මාතෘකාව:"):
            topic = first.replace("මාතෘකාව:", "", 1).strip() or default_topic
            return topic, "\n".join(lines[1:]).strip()
        return default_topic, file_text.strip()

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 420, overlap: int = 80) -> Iterable[str]:
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not normalized:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + max_chars)
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(normalized):
                break
            start = max(0, end - overlap)
        return chunks

    def _load_chunks(self) -> list[TextChunk]:
        if not self.documents_dir.exists():
            raise FileNotFoundError(f"Documents directory missing: {self.documents_dir}")

        chunks: list[TextChunk] = []
        for file_path in sorted(self.documents_dir.glob("*.txt")):
            raw = file_path.read_text(encoding="utf-8")
            topic, content = self._parse_topic(raw, file_path.stem)
            for chunk in self._chunk_text(content):
                chunks.append(TextChunk(topic=topic, source=file_path.name, content=chunk))
        return chunks

    def _build_index(self) -> tuple[faiss.Index, np.ndarray]:
        texts = [chunk.content for chunk in self.chunks]
        vectors = self.embedder.encode(texts)
        vectors = self.embedder.l2_normalize(vectors)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        self.metadata_path.write_text(
            json.dumps([asdict(item) for item in self.chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        np.save(self.vectors_path, vectors)
        return index, vectors

    def _load_index_or_rebuild(self) -> tuple[faiss.Index, np.ndarray]:
        try:
            index = faiss.read_index(str(self.index_path))
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            vectors = np.load(self.vectors_path)
            if len(metadata) != len(self.chunks) or index.ntotal != len(self.chunks) or len(vectors) != len(self.chunks):
                return self._build_index()
            return index, vectors.astype(np.float32)
        except Exception:
            return self._build_index()

    def search(
        self,
        query: str,
        candidate_topics: list[str],
        top_k: int = 3,
        min_score: float = 0.2,
    ) -> list[TextHit]:
        """Step 2 retrieval: text search constrained by top JSON topics."""
        query_vector = self.embedder.encode_query(query)
        query_vector = self.embedder.l2_normalize(query_vector)
        query_norm = self._normalize_text(query)

        allowed = set(topic.strip() for topic in candidate_topics if topic.strip())
        if allowed:
            valid_indices = [idx for idx, chunk in enumerate(self.chunks) if chunk.topic in allowed]
        else:
            valid_indices = list(range(len(self.chunks)))

        if not valid_indices:
            return []

        subset_vectors = self.vectors[valid_indices].astype(np.float32)
        subset_index = faiss.IndexFlatIP(subset_vectors.shape[1])
        subset_index.add(subset_vectors)

        scan_k = min(max(top_k * 8, top_k), len(valid_indices))
        k = max(1, scan_k)
        scores, indices = subset_index.search(query_vector, k)

        candidates: list[TextHit] = []
        for score, local_idx in zip(scores[0], indices[0]):
            if local_idx < 0:
                continue
            similarity = float(score)

            global_idx = valid_indices[int(local_idx)]
            chunk = self.chunks[global_idx]
            bonus = self._lexical_bonus(query_norm, chunk)
            final_score = similarity + bonus
            if final_score < min_score:
                continue

            candidates.append(
                TextHit(
                    topic=chunk.topic,
                    source=chunk.source,
                    content=chunk.content,
                    score=final_score,
                )
            )

        candidates.sort(key=lambda hit: hit.score, reverse=True)
        return candidates[:top_k]

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _lexical_bonus(self, query_norm: str, chunk: TextChunk) -> float:
        if not query_norm:
            return 0.0

        topic_norm = self._normalize_text(chunk.topic)
        content_norm = self._normalize_text(chunk.content)
        query_tokens = [token for token in query_norm.split() if len(token) >= 2]

        bonus = 0.0
        if topic_norm and (topic_norm in query_norm or query_norm in topic_norm):
            bonus = max(bonus, 0.22)

        if topic_norm and any(token in topic_norm for token in query_tokens):
            bonus = max(bonus, 0.16)

        token_matches = sum(1 for token in query_tokens if token in content_norm or token in topic_norm)
        if token_matches >= 2:
            bonus = max(bonus, 0.10 + min(0.10, 0.02 * token_matches))

        return bonus
