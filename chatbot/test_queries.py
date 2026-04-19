"""Simple hybrid RAG test runner with 20 Sinhala queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chatbot.hybrid_retriever import HybridRetriever
from chatbot.ollama import OllamaClient
from chatbot.prompt import FALLBACK_ANSWER, build_prompt


@dataclass
class QueryCase:
    question: str
    expected_topic: str | None


TEST_CASES: list[QueryCase] = [
    QueryCase("මට දුකයි", "දුක"),
    QueryCase("මට බයයි", "භය"),
    QueryCase("මට කෝපයක් තියෙනවා", "කෝපය"),
    QueryCase("මට තනිවම දැනෙනවා", "අතුරුදන් වීම"),
    QueryCase("විශ්වාසය ගොඩනගාගන්නේ කොහොමද", "විශ්වාසය"),
    QueryCase("හොඳ මිතුරෙක් වෙන්න මොනවා කරන්නද", "මිත්‍රත්වය"),
    QueryCase("සංවාදය දියුණු කරගන්න ක්‍රම කියන්න", "සංවාදය"),
    QueryCase("කාලය කළමනාකරණය කරන්න ක්‍රම", "කාල කළමනාකරණය"),
    QueryCase("මට ඉගෙනීමට සැලැස්මක් දෙන්න", "ඉගෙනීම"),
    QueryCase("ව්‍යායාම කිරීමෙන් ලැබෙන වාසි මොනවාද", "ව්‍යායාම"),
    QueryCase("හොඳ ආහාර පුරුදු මොනවාද", "ආහාර පුරුදු"),
    QueryCase("හොඳ නින්දක් ලබා ගන්න හැටි", "නින්ද"),
    QueryCase("අන් අයව ගෞරවයෙන් සලකන්නේ කොහොමද", "ගෞරවය"),
    QueryCase("හොඳ තීරණ ගන්න ක්‍රම", "තීරණ ගැනීම"),
    QueryCase("අභියෝග වලට මුහුණ දෙන්න උපදෙස්", "අභියෝග"),
    QueryCase("මට motivation නැහැ", "අභිප්‍රේරණය"),
    QueryCase("ආතතිය අඩු කරගන්න හැටි", "ආතතිය"),
    QueryCase("පරිසරය රැකගන්න මොනවා කරන්නද", "පරිසරය"),
    QueryCase("හිසරදයක් තියෙනවා මොකද කරන්නෙ", "හිසරදය"),
    QueryCase("සතුටු ජීවිතයක් ගත කරන්න කොහොමද", "සතුටු ජීවිතය"),
    QueryCase("මට හරිම කනස්සල්ලක් තියෙනවා", "දුක"),
    QueryCase("මම බයෙන් ඉන්නේ", "භය"),
    QueryCase("මට කෙනෙක් නැතිව වගේ දැනෙනවා", "අතුරුදන් වීම"),
    QueryCase("operating system කියන්නේ මොකක්ද", "ඔපරේටින් පද්ධතිය"),
    QueryCase("පරිගණකය කියන්නේ මොකක්ද", "පරිගණකය"),
    QueryCase("API කියන්නේ මොකක්ද", "API"),
    QueryCase("data සහ information අතර වෙනස මොකක්ද", "දත්ත සහ තොරතුරු"),
    QueryCase("චන්ද්‍රිකා කක්ෂ ගණනය කරන differential equations", None),
]


def run_tests(use_ollama: bool = False, model_name: str = "gemma") -> None:
    project_root = Path(__file__).resolve().parents[1]
    retriever = HybridRetriever(project_root=project_root, rebuild=False)
    ollama = OllamaClient() if use_ollama else None

    passed = 0
    print("Hybrid RAG test results")
    print("=" * 60)

    for idx, case in enumerate(TEST_CASES, start=1):
        result = retriever.retrieve(case.question)
        topics = [hit.topic for hit in result.json_hits]

        if case.expected_topic is None:
            ok = len(topics) == 0 or (result.json_hits and result.json_hits[0].score < 0.30)
        else:
            ok = case.expected_topic in topics[:2]

        if ok:
            passed += 1

        answer = "(LLM not run)"
        if use_ollama:
            if not result.context:
                answer = FALLBACK_ANSWER
            else:
                prompt = build_prompt(result.context, case.question)
                try:
                    answer = ollama.generate(prompt=prompt, model=model_name)
                except RuntimeError:
                    answer = FALLBACK_ANSWER

        print(f"{idx:02d}. Q: {case.question}")
        print(f"    Expected: {case.expected_topic}")
        print(f"    Retrieved: {topics[:2]}")
        print(f"    Pass: {ok}")
        if use_ollama:
            print(f"    Answer: {answer}")
        print("-" * 60)

    print(f"Passed: {passed}/{len(TEST_CASES)}")


if __name__ == "__main__":
    # Set to True to validate full retrieval + generation.
    run_tests(use_ollama=False)
