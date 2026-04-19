"""Semantic retriever for structured JSON knowledge."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path

import faiss

from chatbot.embeddings import SinhalaEmbedder


@dataclass
class JsonEntry:
    """Structured knowledge entry."""

    topic: str
    keywords: list[str]
    questions: list[str]
    content: str


@dataclass
class JsonHit:
    """Retrieved JSON topic match."""

    topic: str
    content: str
    score: float


@dataclass
class JsonVectorRecord:
    """One semantic view mapped back to a topic."""

    topic: str
    view_type: str
    text: str


class JsonRetriever:
    """FAISS retriever over structured JSON entries."""

    def __init__(
        self,
        knowledge_path: Path,
        index_path: Path,
        metadata_path: Path,
        rebuild: bool = False,
    ) -> None:
        self.knowledge_path = knowledge_path
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.embedder = SinhalaEmbedder()
        self.topic_map: dict[str, JsonEntry] = {}
        self.vector_records: list[JsonVectorRecord] = []

        self.entries = self._load_entries()
        if not self.entries:
            raise ValueError("No valid entries found in knowledge.json")

        self.topic_map = {entry.topic: entry for entry in self.entries}
        self.vector_records = self._build_vector_records()

        if rebuild or not self.index_path.exists() or not self.metadata_path.exists():
            self.index = self._build_index()
        else:
            self.index = self._load_index_or_rebuild()

    def _load_entries(self) -> list[JsonEntry]:
        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"Knowledge file not found: {self.knowledge_path}")

        raw = json.loads(self.knowledge_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("knowledge.json must contain a list")

        entries: list[JsonEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            content = str(item.get("content", "")).strip()
            keywords = [str(x).strip() for x in item.get("keywords", []) if str(x).strip()]
            questions = [str(x).strip() for x in item.get("questions", []) if str(x).strip()]
            if topic and content:
                entries.append(
                    JsonEntry(topic=topic, keywords=keywords, questions=questions, content=content)
                )
        return entries

    def _build_vector_records(self) -> list[JsonVectorRecord]:
        records: list[JsonVectorRecord] = []
        for entry in self.entries:
            records.append(JsonVectorRecord(topic=entry.topic, view_type="topic", text=entry.topic))

            for keyword in entry.keywords:
                if keyword:
                    records.append(
                        JsonVectorRecord(topic=entry.topic, view_type="keyword", text=keyword)
                    )

            for question in entry.questions:
                if question:
                    records.append(
                        JsonVectorRecord(topic=entry.topic, view_type="question", text=question)
                    )

            records.append(JsonVectorRecord(topic=entry.topic, view_type="content", text=entry.content))
        return records

    def _build_index(self) -> faiss.Index:
        texts = [record.text for record in self.vector_records]
        vectors = self.embedder.encode(texts)
        vectors = self.embedder.l2_normalize(vectors)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        self.metadata_path.write_text(
            json.dumps([asdict(item) for item in self.vector_records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return index

    def _load_index_or_rebuild(self) -> faiss.Index:
        try:
            index = faiss.read_index(str(self.index_path))
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            if len(metadata) != len(self.vector_records) or index.ntotal != len(self.vector_records):
                return self._build_index()
            return index
        except Exception:
            return self._build_index()

    def search(self, query: str, top_k: int = 2, min_score: float = 0.35) -> list[JsonHit]:
        """Step 1 retrieval: return top-k semantic JSON topics."""
        query_vector = self.embedder.encode_query(query)
        query_vector = self.embedder.l2_normalize(query_vector)

        scan_k = min(max(8, top_k * 8), self.index.ntotal)
        scores, indices = self.index.search(query_vector, scan_k)

        topic_scores: dict[str, float] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            similarity = float(score)
            record = self.vector_records[int(idx)]
            current = topic_scores.get(record.topic, -1.0)
            if similarity > current:
                topic_scores[record.topic] = similarity

        # Lexical reranking helps exact or near-exact Sinhala user phrasing map to the right topic.
        query_norm = self._normalize_text(query)
        for entry in self.entries:
            lexical = self._lexical_match_score(query_norm, entry)
            if lexical <= 0.0:
                continue
            current = topic_scores.get(entry.topic, -1.0)
            topic_scores[entry.topic] = max(current, lexical)

        ranked = sorted(topic_scores.items(), key=lambda item: item[1], reverse=True)

        hits: list[JsonHit] = []
        for topic, similarity in ranked[:top_k]:
            if similarity < min_score:
                continue
            entry = self.topic_map[topic]
            hits.append(JsonHit(topic=topic, content=entry.content, score=similarity))
        return hits

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _lexical_match_score(self, query_norm: str, entry: JsonEntry) -> float:
        if not query_norm:
            return 0.0

        best = 0.0
        topic_norm = self._normalize_text(entry.topic)
        if topic_norm and (query_norm in topic_norm or topic_norm in query_norm):
            best = max(best, 0.70)

        for keyword in entry.keywords:
            keyword_norm = self._normalize_text(keyword)
            if keyword_norm and keyword_norm in query_norm:
                best = max(best, 0.78)

        for question in entry.questions:
            question_norm = self._normalize_text(question)
            if not question_norm:
                continue
            if query_norm == question_norm:
                best = max(best, 0.98)
                continue
            if query_norm in question_norm or question_norm in query_norm:
                best = max(best, 0.90)
                continue
            ratio = SequenceMatcher(None, query_norm, question_norm).ratio()
            if ratio >= 0.84:
                best = max(best, 0.82)

        return best
