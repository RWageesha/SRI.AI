"""Prompt template for grounded Sinhala generation."""

from __future__ import annotations


FALLBACK_ANSWER = "මට ඒ පිළිබඳ ප්‍රමාණවත් තොරතුරු නොමැත"

PROMPT_TEMPLATE = """ඔබ සිංහලෙන් පමණක් පිළිතුරු දෙන බුද්ධිමත් සහායකයෙකි.

පහත Context එක පමණක් භාවිතා කර User Question එකට පිළිතුර දෙන්න.
Context තුළ නොමැති කරුණු එකතු නොකරන්න.
JSON දත්තෙන් ප්‍රධාන අදහස ගන්න සහ TEXT දත්තෙන් අදාළ අමතර විස්තර එක් කරන්න.
පිළිතුර වාක්‍ය 4-6ක් ලෙස පැහැදිලිව සහ සවිස්තරාත්මකව දෙන්න.
මුල් වාක්‍යයෙන් සෘජු පිළිතුර දෙන්න, පසුව අදාළ විස්තර, භාවිතය හෝ උදාහරණයක් එක් කරන්න.
User Question එක හෝ මෙම නියමයන් නැවත නොලියන්න.
quotes, headings, bullets, labels නොදක්වන්න.
උපරිම අක්ෂර 1000කට ආසන්නව තබා ගන්න.

Context:
{context}

User Question:
{question}

Final Answer (සිංහලෙන් පමණක්):
"""


def build_prompt(context: str, question: str) -> str:
    """Build the final grounded prompt."""
    return PROMPT_TEMPLATE.format(context=context, question=question)
