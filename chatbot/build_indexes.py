"""Build or rebuild FAISS indexes for JSON and text corpora."""

from __future__ import annotations

from pathlib import Path

from chatbot.hybrid_retriever import HybridRetriever


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    retriever = HybridRetriever(project_root=project_root, rebuild=True)

    print("JSON index rebuilt:", project_root / "vectorstore" / "json_index.faiss")
    print("Text index rebuilt:", project_root / "vectorstore" / "text_index.faiss")
    print("JSON topics:", len(retriever.json_retriever.entries))
    print("Text chunks:", len(retriever.text_retriever.chunks))


if __name__ == "__main__":
    main()
