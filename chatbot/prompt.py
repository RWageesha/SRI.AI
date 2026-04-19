"""Prompt template for grounded Sinhala generation."""

from __future__ import annotations


FALLBACK_ANSWER = "මට ඒ පිළිබඳ ප්‍රමාණවත් තොරතුරු නොමැත"

PROMPT_TEMPLATE = """ඔබ සිංහලෙන් පමණක් පිළිතුරු දෙන බුද්ධිමත් සහායකයෙකි.

පහත Context එක පමණක් භාවිතා කර User Question එකට පිළිතුර දෙන්න.
Context තුළ නොමැති කරුණු එකතු නොකරන්න.
පිළිතුර පැහැදිලිව වාක්‍ය 3-6ක් ලෙස දෙන්න. අවශ්‍ය නම් අංකිත පියවර දෙන්න.

Context:
{context}

User Question:
{question}

Answer:
"""


def build_prompt(context: str, question: str) -> str:
    """Build the final grounded prompt."""
    return PROMPT_TEMPLATE.format(context=context, question=question)
