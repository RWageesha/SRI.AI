"""Hybrid RAG retriever: JSON semantic retrieval + text semantic retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chatbot.json_retriever import JsonHit, JsonRetriever
from chatbot.text_retriever import TextHit, TextRetriever


@dataclass
class HybridResult:
    """Unified retrieval result passed to prompt builder."""

    context: str
    json_hits: list[JsonHit]
    text_hits: list[TextHit]


class HybridRetriever:
    """Implements assignment flow: Step1 JSON -> Step2 Text -> Step3 merge."""

    def __init__(self, project_root: Path, rebuild: bool = False) -> None:
        self.project_root = project_root

        self.json_retriever = JsonRetriever(
            knowledge_path=project_root / "data" / "knowledge.json",
            index_path=project_root / "vectorstore" / "json_index.faiss",
            metadata_path=project_root / "vectorstore" / "json_metadata.json",
            rebuild=rebuild,
        )
        self.text_retriever = TextRetriever(
            documents_dir=project_root / "data" / "documents",
            index_path=project_root / "vectorstore" / "text_index.faiss",
            metadata_path=project_root / "vectorstore" / "text_metadata.json",
            vectors_path=project_root / "vectorstore" / "text_vectors.npy",
            rebuild=rebuild,
        )

    def retrieve(self, query: str) -> HybridResult:
        """Retrieve context using strict hybrid flow and return merged context."""
        json_hits = self.json_retriever.search(query=query, top_k=2)
        top_topics = [hit.topic for hit in json_hits]
        top_json_score = json_hits[0].score if json_hits else 0.0

        constrained_text_hits = self.text_retriever.search(
            query=query,
            candidate_topics=top_topics,
            top_k=3,
        )
        text_hits = constrained_text_hits

        # Global fallback should be conservative to preserve old-topic quality.
        if not constrained_text_hits:
            # If JSON is already highly confident, avoid mixing in unrelated global text.
            if top_json_score >= 0.75:
                text_hits = []
            else:
                global_text_hits = self.text_retriever.search(
                    query=query,
                    candidate_topics=[],
                    top_k=4,
                    min_score=0.28,
                )
                if global_text_hits:
                    primary_topic = self._primary_topic(global_text_hits)
                    text_hits = [hit for hit in global_text_hits if hit.topic == primary_topic][:3]
                    if primary_topic and text_hits:
                        same_topic_json = [hit for hit in json_hits if hit.topic == primary_topic]
                        if same_topic_json:
                            json_hits = same_topic_json[:1]
                        else:
                            entry = self.json_retriever.topic_map.get(primary_topic)
                            if entry is not None:
                                json_hits = [
                                    JsonHit(
                                        topic=primary_topic,
                                        content=entry.content,
                                        score=max(top_json_score, global_text_hits[0].score),
                                    )
                                ]
                            elif global_text_hits[0].score >= 0.45:
                                # Topic exists only in text docs: synthesize a compact JSON-style hit.
                                json_hits = [
                                    JsonHit(
                                        topic=primary_topic,
                                        content=text_hits[0].content,
                                        score=global_text_hits[0].score,
                                    )
                                ]

        # If JSON confidence is low, allow global search to override only when clearly better.
        elif top_json_score < 0.30 and constrained_text_hits[0].score < 0.30:
            global_text_hits = self.text_retriever.search(
                query=query,
                candidate_topics=[],
                top_k=4,
                min_score=0.30,
            )
            if global_text_hits and global_text_hits[0].score >= constrained_text_hits[0].score + 0.08:
                primary_topic = self._primary_topic(global_text_hits)
                text_hits = [hit for hit in global_text_hits if hit.topic == primary_topic][:3]
                if primary_topic and text_hits:
                    same_topic_json = [hit for hit in json_hits if hit.topic == primary_topic]
                    if same_topic_json:
                        json_hits = same_topic_json[:1]
                    else:
                        entry = self.json_retriever.topic_map.get(primary_topic)
                        if entry is not None:
                            json_hits = [
                                JsonHit(
                                    topic=primary_topic,
                                    content=entry.content,
                                    score=max(top_json_score, global_text_hits[0].score),
                                )
                            ]
                        elif global_text_hits[0].score >= 0.45:
                            json_hits = [
                                JsonHit(
                                    topic=primary_topic,
                                    content=text_hits[0].content,
                                    score=global_text_hits[0].score,
                                )
                            ]

        # Recover from incorrect topic gating when constrained text evidence is weak.
        elif constrained_text_hits[0].score < 0.45:
            global_text_hits = self.text_retriever.search(
                query=query,
                candidate_topics=[],
                top_k=4,
                min_score=0.30,
            )
            if global_text_hits and global_text_hits[0].score >= constrained_text_hits[0].score + 0.15:
                primary_topic = self._primary_topic(global_text_hits)
                text_hits = [hit for hit in global_text_hits if hit.topic == primary_topic][:3]
                if primary_topic and text_hits:
                    same_topic_json = [hit for hit in json_hits if hit.topic == primary_topic]
                    if same_topic_json:
                        json_hits = same_topic_json[:1]
                    else:
                        entry = self.json_retriever.topic_map.get(primary_topic)
                        if entry is not None:
                            json_hits = [
                                JsonHit(
                                    topic=primary_topic,
                                    content=entry.content,
                                    score=max(top_json_score, global_text_hits[0].score),
                                )
                            ]
                        else:
                            json_hits = [
                                JsonHit(
                                    topic=primary_topic,
                                    content=text_hits[0].content,
                                    score=global_text_hits[0].score,
                                )
                            ]

        # JSON may miss newly-added text-only topics; synthesize a topic from text retrieval.
        if not json_hits and text_hits:
            primary_topic = self._primary_topic(text_hits)
            if primary_topic:
                topic_hits = [hit for hit in text_hits if hit.topic == primary_topic]
                best_hit = topic_hits[0] if topic_hits else text_hits[0]
                if best_hit.score >= 0.45:
                    json_hits = [
                        JsonHit(topic=primary_topic, content=best_hit.content, score=best_hit.score)
                    ]
                    text_hits = topic_hits[:3] if topic_hits else text_hits

        context_parts: list[str] = []
        if json_hits:
            context_parts.append("[JSON දත්ත සාරාංශ]")
            for hit in json_hits:
                context_parts.append(f"මාතෘකාව: {hit.topic}")
                context_parts.append(f"තොරතුර: {hit.content}")

        if text_hits:
            context_parts.append("\n[TEXT දත්ත විස්තර]")
            for hit in text_hits:
                context_parts.append(f"මූලාශ්‍රය: {hit.source}")
                context_parts.append(f"මාතෘකාව: {hit.topic}")
                context_parts.append(f"අන්තර්ගතය: {hit.content}")

        context = "\n".join(context_parts).strip()
        return HybridResult(context=context, json_hits=json_hits, text_hits=text_hits)

    @staticmethod
    def _primary_topic(text_hits: list[TextHit]) -> str:
        """Pick dominant topic by summed similarity score."""
        topic_scores: dict[str, float] = {}
        for hit in text_hits:
            topic_scores[hit.topic] = topic_scores.get(hit.topic, 0.0) + hit.score
        if not topic_scores:
            return ""
        return max(topic_scores.items(), key=lambda item: item[1])[0]
